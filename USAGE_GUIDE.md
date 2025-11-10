# Volume Accumulation Dashboard - Usage Guide

Complete guide to using the volume anomaly detection system.

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Bootstrap historical data (takes a few hours)
uv run bootstrap

# 3. Start dashboard
uv run server

# 4. Open browser
# Navigate to: http://localhost:8000
```

## Detailed Workflow

### Phase 1: Historical Data Collection

The system needs historical data to establish baseline volume averages.

```bash
# Collect default 30 days
uv run bootstrap

# Or specify custom period
uv run bootstrap 7   # 7 days
uv run bootstrap 60  # 60 days
```

**What happens during bootstrap:**
1. Connects to all 7 exchanges
2. Fetches market list for each exchange
3. Downloads daily OHLCV data for each trading pair
4. Maps tokens to contract addresses
5. Aggregates volumes by token ID
6. Saves to JSON files in `data/` directory

**Progress tracking:**
- Check `data/bootstrap/progress_*.json` for per-exchange progress
- Bootstrap can be stopped and resumed anytime
- Failed pairs are logged in progress file

**Expected time:**
- 7 days: 1-2 hours per exchange
- 30 days: 4-8 hours per exchange
- Depends on: number of pairs, rate limits, network speed

### Phase 2: Real-time Monitoring

Once historical data is collected, start monitoring for spikes.

#### Option A: Dashboard Server (Recommended)

Start the web server with built-in monitoring:

```bash
uv run server
```

This starts:
- FastAPI web server on port 8000
- Real-time volume monitor
- WebSocket broadcast for dashboard updates

Access dashboard at: http://localhost:8000

#### Option B: Standalone Monitor

Run just the monitoring engine (no web UI):

```bash
uv run monitor
```

This prints alerts to console as they occur.

## Understanding the Data

### Token Identification

Tokens are uniquely identified across exchanges:

```
Format: {SYMBOL}_{CONTRACT}_{CHAIN}

Examples:
- BTC_native_bitcoin
- ETH_native_ethereum
- USDT_0xdAC17F958D2ee523a2206206994597C13D831ec7_ethereum
- PEPE_0x6982508145454Ce325dDbE47a25d4ec3d2311933_ethereum
```

This prevents confusion between tokens with same ticker on different chains.

### Volume Calculation

**15-Minute Window:**
- System tracks cumulative volume in rolling 15-minute windows
- Window resets every 15 minutes
- Volume is aggregated across all exchanges

**Daily Average:**
- Calculated from historical data
- Multiple timeframes: 1d, 10d, 20d, 30d, 50d, 100d, 150d, 200d, 365d
- Example: "30d avg" = average of last 30 daily volumes

**Spike Ratio:**
```
Spike Ratio = Current 15min Volume / Average Daily Volume

Examples:
- 1.0x = 15 minutes = 1 full day average
- 2.5x = 15 minutes = 2.5 days average
- 10.0x = 15 minutes = 10 days average (extreme!)
```

### Alert Severities

| Severity | Threshold | Meaning |
|----------|-----------|---------|
| **Extreme** | ≥ 5.0x | 15min = 5+ days volume |
| **High** | ≥ 2.0x | 15min = 2-5 days volume |
| **Medium** | ≥ 1.0x | 15min = 1-2 days volume |
| **Low** | ≥ 0.5x | 15min = 12-24 hours volume |
| Normal | < 0.5x | Typical activity |

## Dashboard Features

### 1. Volume Spike Alerts

Top section shows active alerts:

```
🔥🔥🔥 TOKEN-X
7.2x
15min Volume: $50,000,000
1d Avg: $7,000,000
Dominant: binance (60.0%)
```

**What to look for:**
- **High spike ratios** (>5x) indicate massive activity
- **Dominant exchange >80%** might be single-exchange event
- **Spread volume** across exchanges is more significant

### 2. Top Tokens Table

Shows top 50 tokens by current 15min volume:

| Rank | Token | 15min Volume | Dominant Exchange | Share % | Trend |
|------|-------|--------------|-------------------|---------|-------|
| 1 | BTC | $150M | binance | 55% | ● |
| 2 | ETH | $120M | coinbase | 48% | ● |
| 3 | PEPE | $45M | binance | 72% | ● |

**Features:**
- **New tokens** highlighted in blue when they first appear
- **Trend indicator** shows if volume is elevated
- **Auto-updates** every 20 seconds via WebSocket

### 3. Live Status

Header shows:
- **Connection status**: Green = connected, Red = disconnected
- **Current window time**: When current 15min window started
- **Active tokens**: Number of tokens with volume this window

## Trading Use Cases

### Use Case 1: Early Spike Detection

**Goal:** Catch volume spikes before broader market

**Steps:**
1. Monitor dashboard for Extreme alerts (🔥🔥🔥)
2. Verify spike across multiple timeframes (1d, 10d, 30d all elevated)
3. Check it's not single-exchange anomaly
4. Research the token (news, Twitter, etc.)
5. Act within 15-minute window

**Example:**
```
🔥🔥🔥 NEWTOKEN
12.5x spike
$80M in 15min vs $6.4M daily avg
Across 4 exchanges

→ Strong signal: investigate immediately
```

### Use Case 2: Exchange Listing Detection

**Goal:** Identify tokens getting listed on major exchanges

**Pattern:**
- Sudden volume spike on ONE exchange
- Token previously traded elsewhere
- High dominant exchange share (>90%)

**Example:**
```
TOKEN-Y
8.0x spike
Dominant: binance (94%)

→ Likely: Binance just listed this token
```

### Use Case 3: Accumulation Phase Detection

**Goal:** Spot gradual whale accumulation

**Pattern:**
- Consistent medium alerts (1-2x) over multiple windows
- Volume spread across exchanges
- No news or obvious catalyst

**Example:**
```
TOKEN-Z
1.5x spike (repeated over last 3 windows)
Evenly distributed: binance 35%, coinbase 32%, okx 33%

→ Possible: Smart money accumulating
```

### Use Case 4: News/Event Confirmation

**Goal:** Validate breaking news impact

**Pattern:**
- Spike coincides with announcement
- Multiple exchanges show increased volume
- Spike ratio >3x

**Use:**
- Confirms news is impactful
- Gauge market reaction speed
- Time entry/exit

## API Usage

### REST Endpoints

**Health Check:**
```bash
curl http://localhost:8000/api/health
```

**Get Alerts:**
```bash
curl http://localhost:8000/api/alerts
```

**Top Tokens:**
```bash
curl "http://localhost:8000/api/top-tokens?limit=20"
```

**Token Details:**
```bash
curl http://localhost:8000/api/token/BTC_native_bitcoin
```

**System Stats:**
```bash
curl http://localhost:8000/api/stats
```

### WebSocket Connection

Connect to `ws://localhost:8000/ws` for real-time updates.

**JavaScript example:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  if (message.type === 'alerts') {
    console.log('New alerts:', message.data);
  }

  if (message.type === 'top_tokens') {
    console.log('Top tokens:', message.data);
  }
};
```

**Python example:**
```python
import asyncio
import websockets
import json

async def monitor():
    async with websockets.connect('ws://localhost:8000/ws') as ws:
        async for message in ws:
            data = json.loads(message)
            if data['type'] == 'alerts':
                for alert in data['data']:
                    print(f"Alert: {alert['symbol']} - {alert['comparisons']['1d']['spike_ratio']}x")

asyncio.run(monitor())
```

## Configuration

### Modify Exchanges

Edit `vol_accum_dashboard/config.py`:

```python
EXCHANGES = [
    "binance",      # Keep
    "coinbase",     # Keep
    "okx",          # Remove if too many rate limits
    "bybit",        # Keep
    "kraken",       # Keep
    "kucoin",       # Optional
    "gateio",       # Optional
]
```

### Adjust Time Windows

```python
# Change comparison timeframes
COMPARISON_TIMEFRAMES = [1, 7, 30, 90, 365]  # Simplified

# Change real-time window
REALTIME_WINDOW_MINUTES = 10  # 10-minute windows instead of 15

# Change calculation frequency
CALCULATION_INTERVAL_SECONDS = 30  # Check every 30s instead of 60s
```

### Modify Alert Thresholds

```python
SPIKE_THRESHOLDS = {
    "extreme": 10.0,   # More strict
    "high": 5.0,
    "medium": 2.0,
    "low": 1.0,
}
```

## Data Management

### Storage Location

```
data/
├── tokens/
│   ├── token_registry.json          # All known tokens
│   └── volumes/
│       └── BTC_native_bitcoin/
│           ├── daily_2024-10-11.json
│           ├── daily_2024-10-12.json
│           └── ...
├── live/
│   ├── current_15min_volumes.json   # Current window state
│   └── active_alerts.json            # Active alerts
├── snapshots/
│   └── snapshot_2025-11-10_12-00.json
└── bootstrap/
    ├── progress_binance.json
    └── binance/
        └── 2024-10-11.json
```

### Disk Space

Approximate storage requirements:

- **7 days, 500 tokens**: ~50 MB
- **30 days, 1000 tokens**: ~250 MB
- **365 days, 2000 tokens**: ~3 GB

### Backup Data

```bash
# Backup all data
tar -czf backup-$(date +%Y%m%d).tar.gz data/

# Backup only volume data (skip bootstrap)
tar -czf volumes-$(date +%Y%m%d).tar.gz data/tokens/
```

### Clean Old Data

```bash
# Remove bootstrap data after collection
rm -rf data/bootstrap/

# Keep only last 30 days
# (Manual script needed - or will auto-manage in future version)
```

## Troubleshooting

### Issue: No alerts showing

**Possible causes:**
1. Bootstrap not completed
2. Current volumes too low
3. Thresholds too high

**Solutions:**
```bash
# Check if historical data exists
ls data/tokens/volumes/ | head

# Lower thresholds in config.py
SPIKE_THRESHOLDS = {
    "extreme": 2.0,
    "high": 1.0,
    "medium": 0.5,
    "low": 0.25,
}

# Restart server
```

### Issue: Rate limit errors

**Solution 1:** Reduce bootstrap batch size
```python
# In config.py
BOOTSTRAP_BATCH_SIZE = 5  # Instead of 10
```

**Solution 2:** Increase retry delays
```python
RATE_LIMIT_RETRY_DELAYS = [5, 10, 20, 60, 120, 300]
```

**Solution 3:** Bootstrap fewer days initially
```bash
uv run bootstrap 7  # Just 7 days
```

### Issue: WebSocket disconnecting

**Cause:** Network issues or server restarts

**Solution:** Dashboard auto-reconnects (up to 5 attempts)

Check browser console for connection status.

### Issue: Dashboard not updating

**Check:**
1. Server running: `curl http://localhost:8000/api/health`
2. Monitor active: Check server logs
3. Browser WebSocket connected: Check console

**Restart:**
```bash
# Stop server (Ctrl+C)
# Restart
uv run server
# Refresh browser
```

## Performance Tips

1. **Start with fewer exchanges** (e.g., just Binance and Coinbase)
2. **Bootstrap shorter periods** initially (7 days)
3. **Monitor during high-volume hours** (US/EU market hours)
4. **Close unused browser tabs** (reduces WebSocket load)
5. **Run on server** (better uptime than local machine)

## Advanced Usage

### Custom Alerts (Python)

```python
import asyncio
from vol_accum_dashboard.storage.json_store import JSONStore
from vol_accum_dashboard.engine.volume_anomaly_detector import VolumeAnomalyDetector

async def check_token(token_id):
    detector = VolumeAnomalyDetector()
    await detector.load_snapshot()

    alert = await detector.detect_anomalies(token_id, min_severity="high")

    if alert:
        print(f"ALERT: {alert.symbol}")
        print(f"Spike: {alert.comparisons['1d'].spike_ratio}x")
        return True
    return False

# Run
asyncio.run(check_token("BTC_native_bitcoin"))
```

### Export Data

```python
import asyncio
import json
from vol_accum_dashboard.storage.json_store import JSONStore

async def export_token_data(token_id, days=30):
    store = JSONStore()

    # Load historical volumes
    volumes = []
    for day_offset in range(days):
        date = datetime.date.today() - datetime.timedelta(days=day_offset)
        vol = await store.load_daily_volume(token_id, date)
        if vol:
            volumes.append(vol.model_dump())

    # Save to file
    with open(f'{token_id}_export.json', 'w') as f:
        json.dump(volumes, f, indent=2)

asyncio.run(export_token_data("BTC_native_bitcoin"))
```

## Next Steps

1. **Run bootstrap** to collect historical data
2. **Start server** and monitor dashboard
3. **Observe patterns** over a few days
4. **Adjust thresholds** based on your needs
5. **Integrate with trading** (manual or automated)

## Support

For issues or questions:
- Check GitHub Issues
- Review this guide
- Check server logs
- Verify API endpoints with curl

Happy trading!
