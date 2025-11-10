"""Historical data collector for bootstrapping volume data."""

import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Set
import ccxt.async_support as ccxt
from vol_accum_dashboard.config import (
    EXCHANGES,
    BOOTSTRAP_DAYS,
    BOOTSTRAP_BATCH_SIZE,
)
from vol_accum_dashboard.models import (
    DailyVolumeData,
    ExchangeVolume,
    BootstrapProgress,
    TokenMetadata,
)
from vol_accum_dashboard.storage.json_store import JSONStore
from vol_accum_dashboard.utils.rate_limiter import ExchangeRateLimiter
from vol_accum_dashboard.utils.token_mapping import TokenMapper


class HistoricalCollector:
    """Collects historical volume data from exchanges."""

    def __init__(self):
        self.store = JSONStore()
        self.rate_limiter = ExchangeRateLimiter()
        self.token_mapper = TokenMapper()
        self.exchanges: Dict[str, ccxt.Exchange] = {}
        self.token_registry: Dict[str, TokenMetadata] = {}

    async def initialize(self):
        """Initialize exchanges and load token registry."""
        print("Initializing exchanges...")

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

        # Load existing token registry
        self.token_registry = await self.store.load_token_registry()
        print(f"Loaded {len(self.token_registry)} tokens from registry")

    async def close(self):
        """Close all exchange connections."""
        for exchange in self.exchanges.values():
            await exchange.close()
        await self.token_mapper.close()

    async def collect_all_exchanges(self, days: int = BOOTSTRAP_DAYS):
        """
        Collect historical data from all exchanges.

        Args:
            days: Number of days of history to collect
        """
        print(f"\n{'='*60}")
        print(f"Starting historical data collection")
        print(f"Exchanges: {len(EXCHANGES)}")
        print(f"Days: {days}")
        print(f"{'='*60}\n")

        start_time = datetime.now()

        # Collect from each exchange in parallel
        tasks = [
            self.collect_exchange_history(exchange_id, days)
            for exchange_id in self.exchanges.keys()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Print summary
        print(f"\n{'='*60}")
        print("Collection Summary:")
        for exchange_id, result in zip(self.exchanges.keys(), results):
            if isinstance(result, Exception):
                print(f"  {exchange_id}: ✗ FAILED - {result}")
            else:
                print(f"  {exchange_id}: ✓ Completed - {result} pairs")

        elapsed = datetime.now() - start_time
        print(f"\nTotal time: {elapsed}")
        print(f"{'='*60}\n")

    async def collect_exchange_history(self, exchange_id: str, days: int) -> int:
        """
        Collect historical data for a single exchange.

        Args:
            exchange_id: Exchange identifier
            days: Number of days to collect

        Returns:
            Number of pairs processed
        """
        exchange = self.exchanges.get(exchange_id)
        if not exchange:
            raise ValueError(f"Exchange {exchange_id} not initialized")

        print(f"\n[{exchange_id}] Starting collection...")

        # Load existing progress
        progress = await self.store.load_bootstrap_progress(exchange_id)
        if not progress:
            # Fetch markets to get all pairs
            print(f"[{exchange_id}] Fetching markets...")
            markets = await self.rate_limiter.fetch_markets(exchange)
            active_markets = [m for m in markets if m.get('active', True)]

            progress = BootstrapProgress(
                exchange=exchange_id,
                total_pairs=len(active_markets),
                completed_pairs=0,
                last_updated=datetime.now(),
            )

            print(f"[{exchange_id}] Found {len(active_markets)} active pairs")
        else:
            print(f"[{exchange_id}] Resuming from {progress.completed_pairs}/{progress.total_pairs} pairs")
            markets = await self.rate_limiter.fetch_markets(exchange)
            active_markets = [m for m in markets if m.get('active', True)]

        # Process pairs in batches
        pairs_to_process = active_markets[progress.completed_pairs:]

        for i in range(0, len(pairs_to_process), BOOTSTRAP_BATCH_SIZE):
            batch = pairs_to_process[i:i + BOOTSTRAP_BATCH_SIZE]

            # Process batch in parallel
            tasks = [
                self.collect_pair_history(exchange_id, market, days)
                for market in batch
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Update progress
            progress.completed_pairs += len(batch)
            progress.last_updated = datetime.now()

            # Track errors
            for market, result in zip(batch, results):
                if isinstance(result, Exception):
                    error_msg = f"{market['symbol']}: {str(result)}"
                    progress.errors.append(error_msg)
                    print(f"[{exchange_id}] ✗ {error_msg}")

            # Save progress
            await self.store.save_bootstrap_progress(progress)

            # Progress update
            pct = (progress.completed_pairs / progress.total_pairs) * 100
            print(f"[{exchange_id}] Progress: {progress.completed_pairs}/{progress.total_pairs} ({pct:.1f}%)")

        print(f"[{exchange_id}] ✓ Completed!")
        return progress.total_pairs

    async def collect_pair_history(
        self,
        exchange_id: str,
        market: dict,
        days: int,
    ) -> bool:
        """
        Collect historical data for a single trading pair.

        Args:
            exchange_id: Exchange identifier
            market: Market info dict
            days: Number of days to collect

        Returns:
            True if successful
        """
        exchange = self.exchanges[exchange_id]
        symbol = market['symbol']
        base = market['base']
        quote = market['quote']

        try:
            # Map tokens to token IDs
            base_token_id, quote_token_id = await self.token_mapper.map_exchange_pair(
                exchange_id, base, quote
            )

            # Add tokens to registry if not present
            await self._add_token_to_registry(base, base_token_id, exchange_id, symbol)
            await self._add_token_to_registry(quote, quote_token_id, exchange_id, symbol)

            # Fetch OHLCV data for each day
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            for day_offset in range(days):
                current_date = start_date + timedelta(days=day_offset)

                # Check if we already have this data
                existing_base = await self.store.load_daily_volume(base_token_id, current_date)
                existing_quote = await self.store.load_daily_volume(quote_token_id, current_date)

                # Skip if both already exist
                if existing_base and existing_quote:
                    continue

                # Fetch OHLCV data
                since = int(datetime.combine(current_date, datetime.min.time()).timestamp() * 1000)
                ohlcv = await self.rate_limiter.fetch_ohlcv(
                    exchange,
                    symbol,
                    timeframe='1d',
                    since=since,
                    limit=1,
                )

                if not ohlcv:
                    continue

                # Extract volume (OHLCV format: [timestamp, open, high, low, close, volume])
                candle = ohlcv[0]
                volume = candle[5]  # Volume in base currency

                # Convert to USD (approximate using close price)
                close_price = candle[4]
                volume_usd = volume * close_price if quote in ['USDT', 'USDC', 'USD', 'BUSD', 'DAI'] else volume * close_price

                # Store volume for base token
                await self._store_volume_for_token(
                    base_token_id,
                    current_date,
                    exchange_id,
                    symbol,
                    volume_usd,
                )

            return True

        except Exception as e:
            raise Exception(f"Error processing {symbol}: {str(e)}")

    async def _add_token_to_registry(
        self,
        symbol: str,
        token_id: str,
        exchange_id: str,
        pair_symbol: str,
    ):
        """Add or update a token in the registry."""
        if token_id in self.token_registry:
            # Update exchange pairs
            metadata = self.token_registry[token_id]
            if exchange_id not in metadata.exchange_pairs:
                metadata.exchange_pairs[exchange_id] = []
            if pair_symbol not in metadata.exchange_pairs[exchange_id]:
                metadata.exchange_pairs[exchange_id].append(pair_symbol)
                metadata.last_updated = datetime.now().isoformat()
                await self.store.add_token_to_registry(token_id, metadata)
        else:
            # Create new token entry
            token_info = self.token_mapper.get_metadata(symbol)

            if token_info:
                metadata = TokenMetadata(
                    symbol=symbol,
                    name=token_info['name'],
                    contract_address=token_info['contract_address'],
                    chain=token_info['chain'],
                    coingecko_id=token_info['coingecko_id'],
                    exchange_pairs={exchange_id: [pair_symbol]},
                    first_seen=datetime.now().isoformat(),
                    last_updated=datetime.now().isoformat(),
                )
            else:
                metadata = TokenMetadata(
                    symbol=symbol,
                    name=symbol,
                    contract_address=None,
                    chain=None,
                    coingecko_id=None,
                    exchange_pairs={exchange_id: [pair_symbol]},
                    first_seen=datetime.now().isoformat(),
                    last_updated=datetime.now().isoformat(),
                )

            self.token_registry[token_id] = metadata
            await self.store.add_token_to_registry(token_id, metadata)

    async def _store_volume_for_token(
        self,
        token_id: str,
        date: date,
        exchange_id: str,
        pair_symbol: str,
        volume_usd: float,
    ):
        """Store or update volume data for a token."""
        # Load existing data for this date
        existing = await self.store.load_daily_volume(token_id, date)

        if existing:
            # Update existing data
            if exchange_id in existing.exchanges:
                existing.exchanges[exchange_id].pairs[pair_symbol] = volume_usd
                existing.exchanges[exchange_id].total += volume_usd
            else:
                existing.exchanges[exchange_id] = ExchangeVolume(
                    pairs={pair_symbol: volume_usd},
                    total=volume_usd,
                )
            existing.total_volume_usd += volume_usd
            await self.store.save_daily_volume(token_id, date, existing)
        else:
            # Create new data
            volume_data = DailyVolumeData(
                token_id=token_id,
                date=date.isoformat(),
                total_volume_usd=volume_usd,
                exchanges={
                    exchange_id: ExchangeVolume(
                        pairs={pair_symbol: volume_usd},
                        total=volume_usd,
                    )
                }
            )
            await self.store.save_daily_volume(token_id, date, volume_data)

    async def get_collection_stats(self) -> Dict:
        """Get statistics about the collection progress."""
        stats = {}

        for exchange_id in EXCHANGES:
            progress = await self.store.load_bootstrap_progress(exchange_id)
            if progress:
                stats[exchange_id] = {
                    "total_pairs": progress.total_pairs,
                    "completed_pairs": progress.completed_pairs,
                    "percentage": (progress.completed_pairs / progress.total_pairs * 100)
                    if progress.total_pairs > 0 else 0,
                    "errors": len(progress.errors),
                    "last_updated": progress.last_updated.isoformat(),
                }

        return stats
