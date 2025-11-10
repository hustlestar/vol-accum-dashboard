"""Rate limiting and retry logic for exchange API calls."""

import asyncio
import time
from typing import Callable, Any, Optional, TypeVar
from functools import wraps
import ccxt
from vol_accum_dashboard.config import RATE_LIMIT_RETRY_DELAYS, MAX_RETRIES


T = TypeVar('T')


class RateLimitError(Exception):
    """Custom exception for rate limit errors."""
    pass


class RateLimiter:
    """Handles rate limiting and retry logic for API calls."""

    def __init__(self, retry_delays: list[int] = None, max_retries: int = MAX_RETRIES):
        self.retry_delays = retry_delays or RATE_LIMIT_RETRY_DELAYS
        self.max_retries = max_retries
        self.call_counts = {}  # Track calls per exchange
        self.last_call_time = {}  # Track last call time per exchange

    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        exchange_id: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        Execute a function with automatic retry on rate limit errors.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            exchange_id: Exchange identifier for tracking
            **kwargs: Keyword arguments for func

        Returns:
            Result of func

        Raises:
            Exception: If all retries are exhausted
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                # Execute the function
                result = await func(*args, **kwargs)

                # Track successful call
                if exchange_id:
                    self._track_call(exchange_id)

                return result

            except ccxt.RateLimitExceeded as e:
                last_exception = e
                delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]

                print(f"Rate limit exceeded (attempt {attempt + 1}/{self.max_retries}). "
                      f"Waiting {delay}s... Error: {str(e)}")

                await asyncio.sleep(delay)

            except ccxt.DDoSProtection as e:
                last_exception = e
                delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]

                print(f"DDoS protection triggered (attempt {attempt + 1}/{self.max_retries}). "
                      f"Waiting {delay}s... Error: {str(e)}")

                await asyncio.sleep(delay)

            except ccxt.RequestTimeout as e:
                last_exception = e
                delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]

                print(f"Request timeout (attempt {attempt + 1}/{self.max_retries}). "
                      f"Waiting {delay}s... Error: {str(e)}")

                await asyncio.sleep(delay)

            except ccxt.ExchangeNotAvailable as e:
                last_exception = e
                delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]

                print(f"Exchange not available (attempt {attempt + 1}/{self.max_retries}). "
                      f"Waiting {delay}s... Error: {str(e)}")

                await asyncio.sleep(delay)

            except Exception as e:
                # For non-rate-limit errors, raise immediately
                print(f"Non-rate-limit error: {type(e).__name__}: {str(e)}")
                raise

        # All retries exhausted
        error_msg = f"All {self.max_retries} retry attempts exhausted. Last error: {last_exception}"
        print(error_msg)
        raise last_exception if last_exception else Exception(error_msg)

    def _track_call(self, exchange_id: str):
        """Track API call for rate limiting statistics."""
        current_time = time.time()
        self.last_call_time[exchange_id] = current_time

        if exchange_id not in self.call_counts:
            self.call_counts[exchange_id] = 0
        self.call_counts[exchange_id] += 1

    async def sleep_if_needed(self, exchange_id: str, min_delay: float = 0.1):
        """
        Sleep if needed to avoid hitting rate limits.

        Args:
            exchange_id: Exchange identifier
            min_delay: Minimum delay between calls in seconds
        """
        if exchange_id in self.last_call_time:
            elapsed = time.time() - self.last_call_time[exchange_id]
            if elapsed < min_delay:
                await asyncio.sleep(min_delay - elapsed)

    def get_stats(self, exchange_id: str) -> dict:
        """Get rate limiting statistics for an exchange."""
        return {
            "total_calls": self.call_counts.get(exchange_id, 0),
            "last_call_time": self.last_call_time.get(exchange_id),
        }


def with_rate_limit(exchange_id: Optional[str] = None):
    """
    Decorator to add rate limit handling to async functions.

    Usage:
        @with_rate_limit(exchange_id="binance")
        async def fetch_data():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            rate_limiter = RateLimiter()
            return await rate_limiter.execute_with_retry(
                func,
                *args,
                exchange_id=exchange_id,
                **kwargs
            )
        return wrapper
    return decorator


class ExchangeRateLimiter:
    """Rate limiter specifically for CCXT exchanges."""

    def __init__(self):
        self.limiters = {}  # One rate limiter per exchange

    def get_limiter(self, exchange_id: str) -> RateLimiter:
        """Get or create a rate limiter for an exchange."""
        if exchange_id not in self.limiters:
            self.limiters[exchange_id] = RateLimiter()
        return self.limiters[exchange_id]

    async def fetch_ohlcv(
        self,
        exchange: ccxt.Exchange,
        symbol: str,
        timeframe: str = "1d",
        since: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list:
        """Fetch OHLCV data with rate limiting."""
        limiter = self.get_limiter(exchange.id)

        async def _fetch():
            await limiter.sleep_if_needed(exchange.id, exchange.rateLimit / 1000)
            return await exchange.fetch_ohlcv(symbol, timeframe, since, limit)

        return await limiter.execute_with_retry(_fetch, exchange_id=exchange.id)

    async def fetch_markets(self, exchange: ccxt.Exchange) -> list:
        """Fetch markets with rate limiting."""
        limiter = self.get_limiter(exchange.id)

        async def _fetch():
            await limiter.sleep_if_needed(exchange.id, exchange.rateLimit / 1000)
            return await exchange.fetch_markets()

        return await limiter.execute_with_retry(_fetch, exchange_id=exchange.id)

    async def fetch_tickers(self, exchange: ccxt.Exchange, symbols: Optional[list] = None) -> dict:
        """Fetch tickers with rate limiting."""
        limiter = self.get_limiter(exchange.id)

        async def _fetch():
            await limiter.sleep_if_needed(exchange.id, exchange.rateLimit / 1000)
            return await exchange.fetch_tickers(symbols)

        return await limiter.execute_with_retry(_fetch, exchange_id=exchange.id)

    def get_all_stats(self) -> dict:
        """Get statistics for all exchanges."""
        return {
            exchange_id: limiter.get_stats(exchange_id)
            for exchange_id, limiter in self.limiters.items()
        }
