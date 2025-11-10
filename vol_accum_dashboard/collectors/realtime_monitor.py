"""Real-time volume monitoring via WebSocket and REST APIs."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import ccxt.async_support as ccxt

from vol_accum_dashboard.config import (
    EXCHANGES,
    REALTIME_WINDOW_MINUTES,
    CALCULATION_INTERVAL_SECONDS,
)
from vol_accum_dashboard.engine.volume_anomaly_detector import VolumeAnomalyDetector
from vol_accum_dashboard.storage.json_store import JSONStore
from vol_accum_dashboard.utils.rate_limiter import ExchangeRateLimiter
from vol_accum_dashboard.utils.token_mapping import TokenMapper


class RealtimeMonitor:
    """
    Monitors real-time volume across exchanges and detects anomalies.
    """

    def __init__(self):
        self.store = JSONStore()
        self.rate_limiter = ExchangeRateLimiter()
        self.token_mapper = TokenMapper()
        self.anomaly_detector = VolumeAnomalyDetector()

        self.exchanges: Dict[str, ccxt.Exchange] = {}
        self.running = False
        self.window_start_time = datetime.now()

        # Track which tokens to monitor
        self.monitored_tokens: Set[str] = set()

    async def initialize(self):
        """Initialize exchanges and load configuration."""
        print("Initializing real-time monitor...")

        # Initialize exchanges
        for exchange_id in EXCHANGES:
            try:
                exchange_class = getattr(ccxt, exchange_id)
                self.exchanges[exchange_id] = exchange_class({
                    'enableRateLimit': True,
                    'timeout': 30000,
                })
                print(f"✓ Initialized {exchange_id}")
            except Exception as e:
                print(f"✗ Failed to initialize {exchange_id}: {e}")

        # Load token registry to get list of tokens
        registry = await self.store.load_token_registry()
        self.monitored_tokens = set(registry.keys())

        print(f"Monitoring {len(self.monitored_tokens)} tokens across {len(self.exchanges)} exchanges")

    async def close(self):
        """Close all connections."""
        self.running = False

        for exchange in self.exchanges.values():
            await exchange.close()

        await self.token_mapper.close()

    async def start_monitoring(self):
        """Start the real-time monitoring loop."""
        self.running = True
        print(f"\n{'='*60}")
        print("Starting real-time volume monitoring")
        print(f"Window: {REALTIME_WINDOW_MINUTES} minutes")
        print(f"Calculation interval: {CALCULATION_INTERVAL_SECONDS} seconds")
        print(f"{'='*60}\n")

        # Start monitoring tasks for each exchange
        tasks = [
            self.monitor_exchange(exchange_id)
            for exchange_id in self.exchanges.keys()
        ]

        # Start anomaly detection task
        tasks.append(self.anomaly_detection_loop())

        # Start window reset task
        tasks.append(self.window_reset_loop())

        await asyncio.gather(*tasks, return_exceptions=True)

    async def monitor_exchange(self, exchange_id: str):
        """
        Monitor volume for a single exchange.

        Args:
            exchange_id: Exchange identifier
        """
        exchange = self.exchanges[exchange_id]

        print(f"[{exchange_id}] Starting volume monitoring...")

        while self.running:
            try:
                # Fetch current tickers (has 24h volume)
                tickers = await self.rate_limiter.fetch_tickers(exchange)

                # Process each ticker
                for symbol, ticker in tickers.items():
                    try:
                        # Get volume (in base currency)
                        volume_24h = ticker.get('quoteVolume') or ticker.get('baseVolume', 0)

                        if volume_24h == 0:
                            continue

                        # Parse symbol
                        market = exchange.market(symbol)
                        base = market['base']
                        quote = market['quote']

                        # Map to token IDs
                        base_token_id, quote_token_id = await self.token_mapper.map_exchange_pair(
                            exchange_id, base, quote
                        )

                        # Estimate 15-minute volume (rough approximation)
                        # 24h = 96 x 15min periods, so divide by 96
                        volume_15min = volume_24h / 96

                        # Get last price for USD conversion
                        last_price = ticker.get('last', 0)

                        # Convert to USD if quote is stablecoin
                        if quote in ['USDT', 'USDC', 'USD', 'BUSD', 'DAI', 'TUSD', 'FDUSD']:
                            volume_usd = volume_15min
                        else:
                            # Approximate USD value
                            volume_usd = volume_15min * last_price

                        # Update anomaly detector
                        await self.anomaly_detector.update_current_volume(
                            base_token_id,
                            volume_usd,
                            exchange_id,
                        )

                    except Exception as e:
                        # Skip individual ticker errors
                        continue

                # Log progress
                elapsed = datetime.now() - self.window_start_time
                print(f"[{exchange_id}] Updated at {datetime.now().strftime('%H:%M:%S')} "
                      f"(window: {elapsed.total_seconds():.0f}s)")

                # Wait before next fetch (avoid rate limits)
                await asyncio.sleep(60)  # Fetch every minute

            except Exception as e:
                print(f"[{exchange_id}] Error: {e}")
                await asyncio.sleep(30)  # Wait before retry

    async def anomaly_detection_loop(self):
        """Periodically check for volume anomalies."""
        print("[Detector] Starting anomaly detection loop...")

        while self.running:
            try:
                await asyncio.sleep(CALCULATION_INTERVAL_SECONDS)

                # Detect anomalies
                alerts = await self.anomaly_detector.detect_all_anomalies(
                    min_severity="medium",
                    top_n=20,
                )

                if alerts:
                    print(f"\n{'='*60}")
                    print(f"🚨 VOLUME ALERTS ({datetime.now().strftime('%H:%M:%S')})")
                    print(f"{'='*60}")

                    for alert in alerts:
                        # Get 1-day comparison
                        comp_1d = alert.comparisons.get("1d")
                        if comp_1d:
                            severity_emoji = {
                                "extreme": "🔥🔥🔥",
                                "high": "🔥🔥",
                                "medium": "🔥",
                                "low": "⚠️",
                            }.get(comp_1d.severity, "")

                            print(f"\n{severity_emoji} {alert.symbol}")
                            print(f"  15min Volume: ${alert.current_15min_volume:,.0f}")
                            print(f"  1d Avg: ${comp_1d.avg_daily_volume:,.0f}")
                            print(f"  Ratio: {comp_1d.spike_ratio:.2f}x")
                            print(f"  Dominant: {alert.dominant_exchange} ({alert.dominant_exchange_share:.1f}%)")

                    print(f"{'='*60}\n")

                # Save alerts
                alerts_data = [alert.model_dump() for alert in alerts]
                await self.store.save_active_alerts(alerts_data)

                # Save snapshot
                await self.anomaly_detector.save_snapshot()

            except Exception as e:
                print(f"[Detector] Error: {e}")

    async def window_reset_loop(self):
        """Reset the 15-minute window periodically."""
        print(f"[Window] Starting window reset loop ({REALTIME_WINDOW_MINUTES} min)...")

        while self.running:
            try:
                # Wait for window duration
                await asyncio.sleep(REALTIME_WINDOW_MINUTES * 60)

                print(f"\n[Window] Resetting {REALTIME_WINDOW_MINUTES}-minute window...")

                # Reset volumes
                self.anomaly_detector.reset_current_volumes()
                self.window_start_time = datetime.now()

                print(f"[Window] Reset complete at {self.window_start_time.strftime('%H:%M:%S')}\n")

            except Exception as e:
                print(f"[Window] Error: {e}")

    async def get_current_alerts(self) -> List[Dict]:
        """Get current active alerts."""
        return await self.store.load_active_alerts()

    async def get_top_tokens(self, top_n: int = 50) -> List[Dict]:
        """Get top tokens by current volume."""
        return await self.anomaly_detector.get_top_tokens_by_volume(top_n)


class WebSocketMonitor:
    """
    Alternative monitor using WebSocket streams for lower latency.
    Note: Requires ccxt.pro which has better WebSocket support.
    """

    def __init__(self):
        self.store = JSONStore()
        self.anomaly_detector = VolumeAnomalyDetector()
        self.token_mapper = TokenMapper()
        # Would use ccxt.pro for WebSocket support
        # For now, REST API with polling is more reliable

    async def start_websocket_monitoring(self):
        """Start WebSocket-based monitoring (future enhancement)."""
        # TODO: Implement WebSocket monitoring with ccxt.pro
        # This would provide sub-second latency for volume updates
        pass
