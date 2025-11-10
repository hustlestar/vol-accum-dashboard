# Volume Accumulation Dashboard

Real-time crypto volume anomaly detection system that identifies tokens with unusual volume spikes across multiple exchanges.

## Overview

This system monitors volume across 7 major crypto exchanges (Binance, Coinbase, OKX, Bybit, Kraken, KuCoin, Gate.io) and detects when a token's 15-minute volume equals or exceeds its historical daily average - a strong signal of sudden interest or breaking news.

### Key Features

- **Real-time Monitoring**: Track volume across all major exchanges with sub-minute latency
- **Multi-Timeframe Comparison**: Compare current 15min volume against 1, 10, 20, 30, 50, 100, 150, 200, and 365-day averages
- **Token Mapping**: Unified token identification across exchanges using contract addresses
- **Visual Dashboard**: Clean, real-time UI showing top tokens and volume spikes
- **Historical Bootstrap**: Collect 30 days of historical data for baseline comparisons
- **Rate Limit Handling**: Robust retry logic for exchange API 429 errors

## Installation

### Prerequisites

- Python 3.11+
- uv (Python package manager)

### Setup

1. Install dependencies:
```bash
uv sync
```

## Usage

### Step 1: Bootstrap Historical Data

Collect 30 days of historical volume data from all exchanges:

```bash
uv run bootstrap
```

**Note**: This process takes several hours due to rate limits. Progress is saved, so you can stop and resume anytime.

### Step 2: Start Dashboard Server

Start the web dashboard with real-time monitoring:

```bash
uv run server
```

Access the dashboard at: **http://localhost:8000**

## Dashboard Features

### Volume Spike Alerts

Visual cards showing tokens with anomalous volume:

- **Extreme** (=%=%=%): 15min volume e 5x daily average
- **High** (=%=%): 15min volume e 2x daily average
- **Medium** (=%): 15min volume e 1x daily average

### Top Tokens Table

Real-time table of top 50 tokens by 15-minute volume with **new tokens highlighted** in blue.

## Configuration

Edit `vol_accum_dashboard/config.py` to customize exchanges, timeframes, and alert thresholds.

## Data Storage

All data stored locally in `data/` directory as JSON files.

## License

MIT
