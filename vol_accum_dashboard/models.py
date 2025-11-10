"""Data models for volume accumulation dashboard."""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class TokenMetadata(BaseModel):
    """Metadata for a single token."""
    symbol: str
    name: str
    contract_address: Optional[str] = None
    chain: Optional[str] = None
    coingecko_id: Optional[str] = None
    exchange_pairs: Dict[str, List[str]] = Field(default_factory=dict)
    first_seen: str
    last_updated: str


class ExchangeVolume(BaseModel):
    """Volume data for a single exchange."""
    pairs: Dict[str, float] = Field(default_factory=dict)
    total: float = 0.0


class DailyVolumeData(BaseModel):
    """Daily volume data for a token."""
    token_id: str
    date: str
    total_volume_usd: float
    exchanges: Dict[str, ExchangeVolume] = Field(default_factory=dict)


class VolumeComparison(BaseModel):
    """Volume comparison for a specific timeframe."""
    avg_daily_volume: float
    spike_ratio: float
    is_anomaly: bool
    severity: str


class VolumeAlert(BaseModel):
    """Volume spike alert."""
    token_id: str
    symbol: str
    current_15min_volume: float
    timestamp: datetime
    comparisons: Dict[str, VolumeComparison]
    exchanges: Dict[str, float]  # Exchange breakdown
    dominant_exchange: str
    dominant_exchange_share: float


class LiveVolumeSnapshot(BaseModel):
    """Snapshot of current 15-minute volumes."""
    timestamp: datetime
    tokens: Dict[str, float]  # token_id -> volume_usd


class BootstrapProgress(BaseModel):
    """Track progress of historical data collection."""
    exchange: str
    total_pairs: int
    completed_pairs: int
    current_pair: Optional[str] = None
    last_updated: datetime
    errors: List[str] = Field(default_factory=list)


class ExchangePairInfo(BaseModel):
    """Information about a trading pair on an exchange."""
    exchange: str
    symbol: str  # e.g., "BTC/USDT"
    base: str   # e.g., "BTC"
    quote: str  # e.g., "USDT"
    active: bool
    contract_address: Optional[str] = None
    chain: Optional[str] = None


class TokenRegistryEntry(BaseModel):
    """Entry in the token registry."""
    token_id: str
    metadata: TokenMetadata

    @classmethod
    def generate_token_id(cls, symbol: str, contract_address: Optional[str], chain: Optional[str]) -> str:
        """Generate a unique token ID."""
        if contract_address and chain:
            return f"{symbol}_{contract_address}_{chain}"
        elif contract_address:
            return f"{symbol}_{contract_address}_unknown"
        else:
            return f"{symbol}_native_{chain or 'unknown'}"
