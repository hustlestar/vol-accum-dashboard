"""JSON storage layer for volume data with year/month/day structure."""

import json
import asyncio
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Any
import aiofiles
from vol_accum_dashboard.config import (
    TOKENS_DIR,
    VOLUMES_DIR,
    LIVE_DIR,
    SNAPSHOTS_DIR,
    BOOTSTRAP_DIR,
    TOKEN_REGISTRY_FILE,
)
from vol_accum_dashboard.models import (
    TokenMetadata,
    DailyVolumeData,
    TokenRegistryEntry,
    BootstrapProgress,
)


# Global lock for token registry to prevent concurrent writes
_registry_lock = asyncio.Lock()


class JSONStore:
    """Handles all JSON file operations with hierarchical date structure."""

    def __init__(self):
        self.token_registry_path = TOKENS_DIR / TOKEN_REGISTRY_FILE
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Ensure all required directories exist."""
        for directory in [TOKENS_DIR, VOLUMES_DIR, LIVE_DIR, SNAPSHOTS_DIR, BOOTSTRAP_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

    async def save_json(self, file_path: Path, data: Any) -> None:
        """Save data to JSON file asynchronously with atomic write."""
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temp file first, then atomic rename
        temp_path = file_path.with_suffix('.tmp')
        async with aiofiles.open(temp_path, "w") as f:
            await f.write(json.dumps(data, indent=2, default=str))
        # Atomic rename
        temp_path.replace(file_path)

    async def load_json(self, file_path: Path) -> Optional[Dict]:
        """Load data from JSON file asynchronously."""
        if not file_path.exists():
            return None
        try:
            async with aiofiles.open(file_path, "r") as f:
                content = await f.read()
                if not content or content.strip() == "":
                    return None
                return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Error loading {file_path}: {e}")
            return None
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            return None

    # Token Registry Operations
    async def load_token_registry(self) -> Dict[str, TokenMetadata]:
        """Load the token registry with locking."""
        async with _registry_lock:
            data = await self.load_json(self.token_registry_path)
            if not data:
                return {}
            return {
                token_id: TokenMetadata(**metadata)
                for token_id, metadata in data.items()
            }

    async def save_token_registry(self, registry: Dict[str, TokenMetadata]) -> None:
        """Save the token registry with locking."""
        async with _registry_lock:
            data = {
                token_id: metadata.model_dump()
                for token_id, metadata in registry.items()
            }
            await self.save_json(self.token_registry_path, data)

    async def add_token_to_registry(
        self,
        token_id: str,
        metadata: TokenMetadata,
    ) -> None:
        """Add or update a token in the registry with locking."""
        async with _registry_lock:
            # Load current registry
            registry = {}
            data = await self.load_json(self.token_registry_path)
            if data:
                registry = {
                    tid: TokenMetadata(**meta)
                    for tid, meta in data.items()
                }
            
            # Update or add token
            registry[token_id] = metadata
            
            # Save back
            save_data = {
                tid: meta.model_dump()
                for tid, meta in registry.items()
            }
            await self.save_json(self.token_registry_path, save_data)

    # Daily Volume Operations with hierarchical structure
    def get_daily_volume_path(self, token_id: str, date_obj: date) -> Path:
        """
        Get the path for a daily volume file using year/month/day structure.

        Structure: data/volumes/YYYY/MM/DD/{symbol}.json
        Example: data/volumes/2024/11/10/BTC.json

        Note: Uses only the symbol part (before first underscore) from token_id
        """
        year = str(date_obj.year)
        month = f"{date_obj.month:02d}"
        day = f"{date_obj.day:02d}"

        day_dir = VOLUMES_DIR / year / month / day
        day_dir.mkdir(parents=True, exist_ok=True)

        # Extract just the symbol (part before first underscore)
        symbol = token_id.split('_')[0] if '_' in token_id else token_id

        return day_dir / f"{symbol}.json"

    async def save_daily_volume(
        self,
        token_id: str,
        date_obj: date,
        volume_data: DailyVolumeData,
    ) -> None:
        """Save daily volume data for a token."""
        file_path = self.get_daily_volume_path(token_id, date_obj)
        await self.save_json(file_path, volume_data.model_dump())

    async def load_daily_volume(
        self,
        token_id: str,
        date_obj: date,
    ) -> Optional[DailyVolumeData]:
        """Load daily volume data for a token."""
        file_path = self.get_daily_volume_path(token_id, date_obj)
        data = await self.load_json(file_path)
        if data:
            return DailyVolumeData(**data)
        return None

    async def load_daily_volumes_range(
        self,
        token_id: str,
        start_date: date,
        end_date: date,
    ) -> List[DailyVolumeData]:
        """Load daily volumes for a date range."""
        volumes = []
        current_date = start_date
        
        while current_date <= end_date:
            volume_data = await self.load_daily_volume(token_id, current_date)
            if volume_data:
                volumes.append(volume_data)
            
            # Move to next day
            from datetime import timedelta
            current_date = current_date + timedelta(days=1)
            
        return volumes

    async def get_available_volume_days(self, token_id: str) -> List[date]:
        """
        Get all dates with available volume data for a token.
        Scans the year/month/day directory structure.
        """
        dates = []
        
        # Scan all year directories
        if not VOLUMES_DIR.exists():
            return []
            
        for year_dir in sorted(VOLUMES_DIR.iterdir()):
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue
                
            # Scan all month directories
            for month_dir in sorted(year_dir.iterdir()):
                if not month_dir.is_dir() or not month_dir.name.isdigit():
                    continue
                    
                # Scan all day directories
                for day_dir in sorted(month_dir.iterdir()):
                    if not day_dir.is_dir() or not day_dir.name.isdigit():
                        continue
                        
                    # Check if this token exists in this day
                    token_file = day_dir / f"{token_id}.json"
                    if token_file.exists():
                        try:
                            year = int(year_dir.name)
                            month = int(month_dir.name)
                            day = int(day_dir.name)
                            dates.append(date(year, month, day))
                        except ValueError:
                            continue
                            
        return sorted(dates)

    def get_day_directory(self, date_obj: date) -> Path:
        """Get the directory path for a specific day."""
        year = str(date_obj.year)
        month = f"{date_obj.month:02d}"
        day = f"{date_obj.day:02d}"
        return VOLUMES_DIR / year / month / day

    async def get_all_tokens_for_day(self, date_obj: date) -> List[str]:
        """Get all token IDs that have data for a specific day."""
        day_dir = self.get_day_directory(date_obj)
        if not day_dir.exists():
            return []
            
        token_ids = []
        for file_path in day_dir.glob("*.json"):
            # Token ID is the filename without .json
            token_ids.append(file_path.stem)
            
        return token_ids

    # Bootstrap Progress Operations
    def get_bootstrap_progress_path(self, exchange: str) -> Path:
        """Get the path for bootstrap progress file."""
        return BOOTSTRAP_DIR / f"progress_{exchange}.json"

    async def save_bootstrap_progress(self, progress: BootstrapProgress) -> None:
        """Save bootstrap progress."""
        file_path = self.get_bootstrap_progress_path(progress.exchange)
        await self.save_json(file_path, progress.model_dump())

    async def load_bootstrap_progress(self, exchange: str) -> Optional[BootstrapProgress]:
        """Load bootstrap progress."""
        file_path = self.get_bootstrap_progress_path(exchange)
        data = await self.load_json(file_path)
        if data:
            return BootstrapProgress(**data)
        return None

    # Live Data Operations
    async def save_live_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Save current live volume snapshot."""
        file_path = LIVE_DIR / "current_15min_volumes.json"
        await self.save_json(file_path, snapshot)

    async def load_live_snapshot(self) -> Optional[Dict[str, Any]]:
        """Load current live volume snapshot."""
        file_path = LIVE_DIR / "current_15min_volumes.json"
        return await self.load_json(file_path)

    async def save_active_alerts(self, alerts: List[Dict[str, Any]]) -> None:
        """Save active volume alerts."""
        file_path = LIVE_DIR / "active_alerts.json"
        await self.save_json(file_path, alerts)

    async def load_active_alerts(self) -> List[Dict[str, Any]]:
        """Load active volume alerts."""
        file_path = LIVE_DIR / "active_alerts.json"
        data = await self.load_json(file_path)
        return data if data else []

    # Snapshot Operations
    async def save_hourly_snapshot(self, timestamp: datetime, data: Dict[str, Any]) -> None:
        """Save an hourly snapshot."""
        filename = f"snapshot_{timestamp.strftime('%Y-%m-%d_%H-%M')}.json"
        file_path = SNAPSHOTS_DIR / filename
        await self.save_json(file_path, data)

    # Raw Bootstrap Data Operations  
    def get_raw_data_path(self, exchange: str, date_obj: date) -> Path:
        """
        Get path for raw exchange data with hierarchical structure.
        
        Structure: data/bootstrap/{exchange}/YYYY/MM/{date}.json
        """
        exchange_dir = BOOTSTRAP_DIR / exchange / str(date_obj.year) / f"{date_obj.month:02d}"
        exchange_dir.mkdir(parents=True, exist_ok=True)
        return exchange_dir / f"{date_obj.day:02d}.json"

    async def save_raw_exchange_data(
        self,
        exchange: str,
        date_obj: date,
        data: Dict[str, Any],
    ) -> None:
        """Save raw exchange data."""
        file_path = self.get_raw_data_path(exchange, date_obj)
        await self.save_json(file_path, data)

    async def load_raw_exchange_data(
        self,
        exchange: str,
        date_obj: date,
    ) -> Optional[Dict[str, Any]]:
        """Load raw exchange data."""
        file_path = self.get_raw_data_path(exchange, date_obj)
        return await self.load_json(file_path)

    # Cleanup utilities
    async def cleanup_old_data(self, days_to_keep: int = 365):
        """
        Remove volume data older than specified days.
        Keeps directory structure clean.
        """
        from datetime import timedelta
        cutoff_date = date.today() - timedelta(days=days_to_keep)
        
        removed_count = 0
        
        for year_dir in VOLUMES_DIR.iterdir():
            if not year_dir.is_dir():
                continue
                
            year = int(year_dir.name)
            
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir():
                    continue
                    
                month = int(month_dir.name)
                
                for day_dir in month_dir.iterdir():
                    if not day_dir.is_dir():
                        continue
                        
                    day = int(day_dir.name)
                    dir_date = date(year, month, day)
                    
                    if dir_date < cutoff_date:
                        # Remove entire day directory
                        import shutil
                        shutil.rmtree(day_dir)
                        removed_count += 1
                        
        return removed_count
