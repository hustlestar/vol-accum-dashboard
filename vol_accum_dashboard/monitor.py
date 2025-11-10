"""Monitor script for real-time volume tracking."""

import asyncio
from vol_accum_dashboard.collectors.realtime_monitor import RealtimeMonitor


async def run_monitor():
    """Main monitoring function."""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║   Volume Accumulation Dashboard - Real-time Monitor      ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    monitor = RealtimeMonitor()

    try:
        await monitor.initialize()
        await monitor.start_monitoring()

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
    except Exception as e:
        print(f"\n\nError during monitoring: {e}")
        raise
    finally:
        await monitor.close()


def main():
    """Entry point for script."""
    asyncio.run(run_monitor())


if __name__ == "__main__":
    main()
