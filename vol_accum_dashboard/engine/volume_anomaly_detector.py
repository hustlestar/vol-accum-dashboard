"""Volume anomaly detection engine."""

import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
import numpy as np

from vol_accum_dashboard.config import (
    COMPARISON_TIMEFRAMES,
    SPIKE_THRESHOLDS,
    REALTIME_WINDOW_MINUTES,
)
from vol_accum_dashboard.models import (
    VolumeAlert,
    VolumeComparison,
    DailyVolumeData,
)
from vol_accum_dashboard.storage.json_store import JSONStore


class VolumeAnomalyDetector:
    """
    Detects volume anomalies by comparing current short-term volume
    against historical daily averages.
    """

    def __init__(self):
        self.store = JSONStore()
        self.current_volumes: Dict[str, float] = {}  # token_id -> current 15min volume
        self.exchange_volumes: Dict[str, Dict[str, float]] = {}  # token_id -> {exchange_id -> volume}
        self.historical_cache: Dict[str, List[DailyVolumeData]] = {}  # token_id -> daily volumes
        self.last_calculation_time = datetime.now()

    async def update_current_volume(
        self,
        token_id: str,
        volume_usd: float,
        exchange_id: str,
    ):
        """
        Update the current 15-minute volume for a token.

        Args:
            token_id: Unique token identifier
            volume_usd: Volume in USD
            exchange_id: Exchange where the volume occurred
        """
        # Update total volume
        if token_id not in self.current_volumes:
            self.current_volumes[token_id] = 0
        self.current_volumes[token_id] += volume_usd

        # Update exchange breakdown
        if token_id not in self.exchange_volumes:
            self.exchange_volumes[token_id] = {}
        if exchange_id not in self.exchange_volumes[token_id]:
            self.exchange_volumes[token_id][exchange_id] = 0
        self.exchange_volumes[token_id][exchange_id] += volume_usd

    def reset_current_volumes(self):
        """Reset the current 15-minute volume window."""
        self.current_volumes.clear()
        self.exchange_volumes.clear()
        self.last_calculation_time = datetime.now()

    async def load_historical_volumes(
        self,
        token_id: str,
        days: int = max(COMPARISON_TIMEFRAMES),
        force_reload: bool = False,
    ) -> List[DailyVolumeData]:
        """
        Load historical daily volumes for a token.

        Args:
            token_id: Unique token identifier
            days: Number of days to load
            force_reload: Force reload from storage

        Returns:
            List of daily volume data
        """
        # Check cache
        if not force_reload and token_id in self.historical_cache:
            cached = self.historical_cache[token_id]
            if len(cached) >= days:
                return cached[-days:]

        # Load from storage
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        volumes = []
        current_date = start_date

        while current_date <= end_date:
            volume_data = await self.store.load_daily_volume(token_id, current_date)
            if volume_data:
                volumes.append(volume_data)
            current_date += timedelta(days=1)

        # Update cache
        self.historical_cache[token_id] = volumes

        return volumes

    def calculate_average_daily_volume(
        self,
        daily_volumes: List[DailyVolumeData],
        days: int,
    ) -> float:
        """
        Calculate average daily volume for a given number of days.

        Args:
            daily_volumes: List of daily volume data
            days: Number of days to average

        Returns:
            Average daily volume in USD
        """
        if not daily_volumes:
            return 0.0

        # Get the last N days
        recent_volumes = daily_volumes[-days:] if len(daily_volumes) > days else daily_volumes

        if not recent_volumes:
            return 0.0

        # Calculate average
        total_volume = sum(v.total_volume_usd for v in recent_volumes)
        return total_volume / len(recent_volumes)

    def calculate_spike_ratio(
        self,
        current_volume: float,
        avg_daily_volume: float,
    ) -> float:
        """
        Calculate the spike ratio: how many "days worth" of volume in current window.

        Args:
            current_volume: Current 15-minute volume
            avg_daily_volume: Average daily volume

        Returns:
            Spike ratio (e.g., 2.0 means current 15min = 2 days of average volume)
        """
        if avg_daily_volume == 0:
            return 0.0

        return current_volume / avg_daily_volume

    def determine_severity(self, spike_ratio: float) -> str:
        """
        Determine the severity of a volume spike.

        Args:
            spike_ratio: The spike ratio

        Returns:
            Severity level: "extreme", "high", "medium", "low", or "normal"
        """
        for severity, threshold in sorted(
            SPIKE_THRESHOLDS.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            if spike_ratio >= threshold:
                return severity
        return "normal"

    async def detect_anomalies(
        self,
        token_id: str,
        min_severity: str = "low",
    ) -> Optional[VolumeAlert]:
        """
        Detect volume anomalies for a single token.

        Args:
            token_id: Unique token identifier
            min_severity: Minimum severity to report

        Returns:
            VolumeAlert if anomaly detected, None otherwise
        """
        # Get current volume
        current_volume = self.current_volumes.get(token_id, 0)

        if current_volume == 0:
            return None

        # Load historical volumes
        try:
            daily_volumes = await self.load_historical_volumes(token_id)
        except Exception as e:
            print(f"Error loading historical volumes for {token_id}: {e}")
            return None

        if not daily_volumes:
            return None

        # Calculate comparisons for all timeframes
        comparisons = {}
        max_spike_ratio = 0.0

        for days in COMPARISON_TIMEFRAMES:
            avg_daily = self.calculate_average_daily_volume(daily_volumes, days)
            spike_ratio = self.calculate_spike_ratio(current_volume, avg_daily)
            severity = self.determine_severity(spike_ratio)

            comparisons[f"{days}d"] = VolumeComparison(
                avg_daily_volume=avg_daily,
                spike_ratio=spike_ratio,
                is_anomaly=spike_ratio >= SPIKE_THRESHOLDS["medium"],
                severity=severity,
            )

            max_spike_ratio = max(max_spike_ratio, spike_ratio)

        # Check if meets minimum severity
        max_severity = self.determine_severity(max_spike_ratio)
        severity_levels = ["normal", "low", "medium", "high", "extreme"]

        if severity_levels.index(max_severity) < severity_levels.index(min_severity):
            return None

        # Get exchange breakdown
        exchanges = self.exchange_volumes.get(token_id, {})

        # Determine dominant exchange
        dominant_exchange = "unknown"
        dominant_share = 0.0

        if exchanges:
            dominant_exchange = max(exchanges.items(), key=lambda x: x[1])[0]
            dominant_share = (exchanges[dominant_exchange] / current_volume) * 100

        # Get token symbol from registry
        registry = await self.store.load_token_registry()
        symbol = token_id.split("_")[0] if token_id not in registry else registry[token_id].symbol

        # Create alert
        alert = VolumeAlert(
            token_id=token_id,
            symbol=symbol,
            current_15min_volume=current_volume,
            timestamp=datetime.now(),
            comparisons=comparisons,
            exchanges=exchanges,
            dominant_exchange=dominant_exchange,
            dominant_exchange_share=dominant_share,
        )

        return alert

    async def detect_all_anomalies(
        self,
        min_severity: str = "low",
        top_n: Optional[int] = None,
    ) -> List[VolumeAlert]:
        """
        Detect anomalies across all tokens with current volume.

        Args:
            min_severity: Minimum severity to report
            top_n: Return only top N by spike ratio

        Returns:
            List of VolumeAlerts sorted by spike ratio (descending)
        """
        alerts = []

        # Process all tokens with current volume
        tasks = [
            self.detect_anomalies(token_id, min_severity)
            for token_id in self.current_volumes.keys()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, VolumeAlert):
                alerts.append(result)
            elif isinstance(result, Exception):
                print(f"Error detecting anomaly: {result}")

        # Sort by maximum spike ratio (use 1d comparison)
        alerts.sort(
            key=lambda a: a.comparisons.get("1d", VolumeComparison(
                avg_daily_volume=0, spike_ratio=0, is_anomaly=False, severity="normal"
            )).spike_ratio,
            reverse=True
        )

        if top_n:
            alerts = alerts[:top_n]

        return alerts

    async def get_top_tokens_by_volume(
        self,
        top_n: int = 50,
    ) -> List[Dict]:
        """
        Get top tokens by current 15-minute volume.

        Args:
            top_n: Number of top tokens to return

        Returns:
            List of token data sorted by volume
        """
        tokens = []

        for token_id, volume in self.current_volumes.items():
            # Get token metadata
            registry = await self.store.load_token_registry()
            symbol = token_id.split("_")[0] if token_id not in registry else registry[token_id].symbol

            # Get exchange breakdown
            exchanges = self.exchange_volumes.get(token_id, {})
            dominant_exchange = "unknown"
            dominant_share = 0.0

            if exchanges:
                dominant_exchange = max(exchanges.items(), key=lambda x: x[1])[0]
                dominant_share = (exchanges[dominant_exchange] / volume) * 100

            tokens.append({
                "token_id": token_id,
                "symbol": symbol,
                "volume_15min": volume,
                "exchanges": exchanges,
                "dominant_exchange": dominant_exchange,
                "dominant_share": dominant_share,
            })

        # Sort by volume
        tokens.sort(key=lambda t: t["volume_15min"], reverse=True)

        return tokens[:top_n]

    async def save_snapshot(self):
        """Save current state to storage."""
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "volumes": self.current_volumes,
            "exchange_breakdown": self.exchange_volumes,
        }

        await self.store.save_live_snapshot(snapshot)

    async def load_snapshot(self):
        """Load last saved state from storage."""
        snapshot = await self.store.load_live_snapshot()

        if snapshot:
            self.current_volumes = snapshot.get("volumes", {})
            self.exchange_volumes = snapshot.get("exchange_breakdown", {})
            timestamp_str = snapshot.get("timestamp")

            if timestamp_str:
                self.last_calculation_time = datetime.fromisoformat(timestamp_str)

    async def get_top_tokens_by_spike_ratio(
        self,
        top_n: int = 50,
        timeframe_days: int = 30,
    ) -> List[Dict]:
        """
        Get top tokens sorted by spike ratio against historical average.

        Args:
            top_n: Number of top tokens to return
            timeframe_days: Number of days for average calculation (default: 30)

        Returns:
            List of token data sorted by spike ratio (descending)
        """
        tokens = []

        for token_id, volume in self.current_volumes.items():
            try:
                # Load historical volumes
                daily_volumes = await self.load_historical_volumes(token_id, days=timeframe_days)

                if not daily_volumes:
                    continue

                # Calculate average and spike ratio
                avg_daily = self.calculate_average_daily_volume(daily_volumes, timeframe_days)
                spike_ratio = self.calculate_spike_ratio(volume, avg_daily)

                # Get token metadata
                registry = await self.store.load_token_registry()
                symbol = token_id.split("_")[0] if token_id not in registry else registry[token_id].symbol

                # Get exchange breakdown
                exchanges = self.exchange_volumes.get(token_id, {})
                dominant_exchange = "unknown"
                dominant_share = 0.0

                if exchanges:
                    dominant_exchange = max(exchanges.items(), key=lambda x: x[1])[0]
                    dominant_share = (exchanges[dominant_exchange] / volume) * 100

                tokens.append({
                    "token_id": token_id,
                    "symbol": symbol,
                    "volume_15min": volume,
                    "avg_daily_volume": avg_daily,
                    "spike_ratio": spike_ratio,
                    "exchanges": exchanges,
                    "dominant_exchange": dominant_exchange,
                    "dominant_share": dominant_share,
                    "timeframe_days": timeframe_days,
                })

            except Exception as e:
                print(f"Error calculating spike ratio for {token_id}: {e}")
                continue

        # Sort by spike ratio (descending)
        tokens.sort(key=lambda t: t["spike_ratio"], reverse=True)

        return tokens[:top_n]
