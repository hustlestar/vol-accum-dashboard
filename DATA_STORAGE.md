# Data Storage Structure

## Overview

The system uses a hierarchical date-based directory structure for efficient storage and retrieval of volume data.

## Directory Structure

```
data/
├── volumes/                    # Volume data organized by date
│   ├── 2024/
│   │   ├── 11/
│   │   │   ├── 10/           # November 10, 2024
│   │   │   │   ├── BTC_native_bitcoin.json
│   │   │   │   ├── ETH_native_ethereum.json
│   │   │   │   ├── USDT_0xdAC17F958D2ee523a2206206994597C13D831ec7_ethereum.json
│   │   │   │   └── ...       # One file per token per day
│   │   │   ├── 11/           # November 11, 2024
│   │   │   │   └── ...
│   │   ├── 12/               # December
│   │   │   └── ...
│   ├── 2025/
│   │   └── ...
│
├── tokens/
│   └── token_registry.json   # Global token registry
│
├── bootstrap/                 # Historical data collection
│   ├── binance/
│   │   ├── 2024/
│   │   │   ├── 11/
│   │   │   │   ├── 10.json  # Raw data for Nov 10
│   │   │   │   ├── 11.json
│   │   │   │   └── ...
│   │   └── progress_binance.json
│   ├── coinbase/
│   │   └── ...
│
├── live/
│   ├── current_15min_volumes.json   # Current window state
│   └── active_alerts.json            # Active volume alerts
│
└── snapshots/
    ├── snapshot_2024-11-10_12-00.json
    └── ...
```

## Benefits

### Scalability
- **No huge directories**: Each day directory contains only that day's tokens
- **Easy navigation**: Browse by year > month > day
- **Efficient queries**: Load only specific dates needed

### Performance
- **Fast lookups**: Direct path calculation: `volumes/YYYY/MM/DD/{token_id}.json`
- **Parallel access**: Different dates/tokens in separate files
- **Atomic writes**: Temp file + rename prevents corruption

### Maintenance
- **Easy cleanup**: Delete old data by removing year/month folders
- **Selective backup**: Backup specific date ranges
- **Disk space tracking**: See space usage per month/year

## File Formats

### Daily Volume File

Path: `data/volumes/2024/11/10/BTC_native_bitcoin.json`

```json
{
  "token_id": "BTC_native_bitcoin",
  "date": "2024-11-10",
  "total_volume_usd": 15000000000.0,
  "exchanges": {
    "binance": {
      "pairs": {
        "BTC/USDT": 8000000000.0,
        "BTC/BUSD": 2000000000.0
      },
      "total": 10000000000.0
    },
    "coinbase": {
      "pairs": {
        "BTC/USD": 3000000000.0
      },
      "total": 3000000000.0
    },
    "kraken": {
      "pairs": {
        "BTC/USD": 2000000000.0
      },
      "total": 2000000000.0
    }
  }
}
```

### Token Registry

Path: `data/tokens/token_registry.json`

```json
{
  "BTC_native_bitcoin": {
    "symbol": "BTC",
    "name": "Bitcoin",
    "contract_address": null,
    "chain": "bitcoin",
    "coingecko_id": "bitcoin",
    "exchange_pairs": {
      "binance": ["BTC/USDT", "BTC/BUSD"],
      "coinbase": ["BTC/USD"],
      "kraken": ["BTC/USD"]
    },
    "first_seen": "2024-11-10T00:00:00",
    "last_updated": "2024-11-10T12:34:56"
  }
}
```

## Storage Operations

### Writing Data

```python
# Store volume for BTC on Nov 10, 2024
await store.save_daily_volume(
    token_id="BTC_native_bitcoin",
    date=date(2024, 11, 10),
    volume_data=volume_data
)

# Automatically creates: data/volumes/2024/11/10/BTC_native_bitcoin.json
```

### Reading Data

```python
# Load single day
volume = await store.load_daily_volume(
    token_id="BTC_native_bitcoin",
    date=date(2024, 11, 10)
)

# Load date range
volumes = await store.load_daily_volumes_range(
    token_id="BTC_native_bitcoin",
    start_date=date(2024, 11, 1),
    end_date=date(2024, 11, 10)
)
```

### Querying

```python
# Get all dates with data for a token
dates = await store.get_available_volume_days("BTC_native_bitcoin")
# Returns: [date(2024, 11, 10), date(2024, 11, 11), ...]

# Get all tokens with data on a specific day
tokens = await store.get_all_tokens_for_day(date(2024, 11, 10))
# Returns: ["BTC_native_bitcoin", "ETH_native_ethereum", ...]
```

### Cleanup

```python
# Remove data older than 365 days
removed = await store.cleanup_old_data(days_to_keep=365)
print(f"Removed {removed} day directories")
```

## Migration from Old Structure

If you have old data in `data/tokens/volumes/{token_id}/daily_YYYY-MM-DD.json`:

```bash
# Run migration script (if needed in future)
# uv run python scripts/migrate_storage.py
```

## Disk Space

### Estimates

- **Per token per day**: ~1-5 KB (depends on number of exchange pairs)
- **1000 tokens, 30 days**: ~30-150 MB
- **1000 tokens, 365 days**: ~365 MB - 1.8 GB

### Monitoring

```bash
# Check space usage by year
du -h data/volumes/2024

# Check space usage by month
du -h data/volumes/2024/11

# Check space usage by day
du -h data/volumes/2024/11/10
```

## Backup Strategy

### Daily Backup
```bash
# Backup today's data
tar -czf backup_$(date +%Y-%m-%d).tar.gz data/volumes/2024/11/10
```

### Monthly Backup
```bash
# Backup entire month
tar -czf backup_2024-11.tar.gz data/volumes/2024/11
```

### Full Backup
```bash
# Backup everything
tar -czf backup_full.tar.gz data/
```

## Performance Characteristics

- **Write**: O(1) - direct path calculation
- **Read single day**: O(1) - direct file read
- **Read range**: O(n) where n = days in range
- **List dates for token**: O(d) where d = total days of data
- **Concurrent access**: Supported via async I/O + atomic writes

## Locking Strategy

- **Token registry**: Global async lock (prevents corruption from parallel writes)
- **Daily volumes**: No lock needed (one file per token per day)
- **Atomic writes**: Temp file + rename (prevents partial writes)
