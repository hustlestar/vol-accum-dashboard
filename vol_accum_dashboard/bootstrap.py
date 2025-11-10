"""Bootstrap script to collect historical data."""

import asyncio
import sys
from vol_accum_dashboard.collectors.historical_collector import HistoricalCollector
from vol_accum_dashboard.config import BOOTSTRAP_DAYS


async def run_bootstrap():
    """Main bootstrap function."""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║   Volume Accumulation Dashboard - Historical Bootstrap   ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    collector = HistoricalCollector()

    try:
        await collector.initialize()

        # Get days from command line or use default
        days = int(sys.argv[1]) if len(sys.argv) > 1 else BOOTSTRAP_DAYS

        print(f"\nCollecting {days} days of historical data...")
        print("This may take several hours depending on rate limits.\n")

        await collector.collect_all_exchanges(days)

        # Show statistics
        print("\nCollection Statistics:")
        stats = await collector.get_collection_stats()

        for exchange, stat in stats.items():
            print(f"\n{exchange}:")
            print(f"  Completed: {stat['completed_pairs']}/{stat['total_pairs']} pairs")
            print(f"  Progress: {stat['percentage']:.1f}%")
            print(f"  Errors: {stat['errors']}")

        print("\n✓ Bootstrap complete!")
        print("\nNext steps:")
        print("  1. Run 'uv run monitor' to start real-time monitoring")
        print("  2. Run 'uv run server' to start the dashboard")

    except KeyboardInterrupt:
        print("\n\nBootstrap interrupted by user")
    except Exception as e:
        print(f"\n\nError during bootstrap: {e}")
        raise
    finally:
        await collector.close()


def main():
    """Entry point for script."""
    asyncio.run(run_bootstrap())


if __name__ == "__main__":
    main()
