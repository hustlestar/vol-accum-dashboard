"""Configuration and constants for volume accumulation dashboard."""

from pathlib import Path
from typing import List

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
TOKENS_DIR = DATA_DIR / "tokens"
VOLUMES_DIR = DATA_DIR / "volumes"
LIVE_DIR = DATA_DIR / "live"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
BOOTSTRAP_DIR = DATA_DIR / "bootstrap"

# Ensure directories exist
for directory in [DATA_DIR, TOKENS_DIR, VOLUMES_DIR, LIVE_DIR, SNAPSHOTS_DIR, BOOTSTRAP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Exchange configuration
EXCHANGES = [
    "binance",
    "coinbase",
    "okx",
    "bybit",
    "kraken",
    "kucoin",
    "gateio",
]

# Quote currency filter - only track pairs quoted in these
ALLOWED_QUOTE_CURRENCIES = ["USDT"]

# Stablecoins to exclude from tracking
STABLECOINS = [
    "USDT", "USDC", "BUSD", "DAI", "TUSD", "USDD", "FDUSD",
    "UST", "USDP", "GUSD", "LUSD", "FRAX", "SUSD"
]

# Time windows for volume comparison (in days)
COMPARISON_TIMEFRAMES = [1, 10, 20, 30, 50, 100, 150, 200, 365]

# Real-time monitoring settings
REALTIME_WINDOW_MINUTES = 15
CALCULATION_INTERVAL_SECONDS = 60  # How often to check for spikes

# Historical data collection
BOOTSTRAP_DAYS = 30
BOOTSTRAP_BATCH_SIZE = 10  # Number of pairs to fetch in parallel

# Rate limiting
RATE_LIMIT_RETRY_DELAYS = [2, 5, 10, 30, 60, 120]  # seconds
MAX_RETRIES = 6

# Volume spike thresholds
SPIKE_THRESHOLDS = {
    "extreme": 5.0,   # 15min volume >= 5x daily average
    "high": 2.0,      # 15min volume >= 2x daily average
    "medium": 1.0,    # 15min volume >= 1x daily average
    "low": 0.5,       # 15min volume >= 0.5x daily average
}

# API settings
API_HOST = "0.0.0.0"
API_PORT = 8000
WEBSOCKET_PING_INTERVAL = 20  # seconds

# CoinGecko settings (for token mapping)
COINGECKO_API_BASE = "https://api.coingecko.com/api/v3"
COINGECKO_REQUEST_DELAY = 1.2  # seconds between requests (free tier: 50 calls/min)

# Storage settings
SNAPSHOT_INTERVAL_MINUTES = 60  # Save snapshots every hour
TOKEN_REGISTRY_FILE = "token_registry.json"

# Data retention
DATA_RETENTION_DAYS = 365  # Keep data for 1 year by default
