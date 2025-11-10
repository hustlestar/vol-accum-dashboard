"""FastAPI server for volume dashboard."""

import asyncio
from datetime import datetime
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from vol_accum_dashboard.config import API_HOST, API_PORT, WEBSOCKET_PING_INTERVAL
from vol_accum_dashboard.collectors.realtime_monitor import RealtimeMonitor
from vol_accum_dashboard.storage.json_store import JSONStore


# Global monitor instance
monitor: Optional[RealtimeMonitor] = None
connected_clients: List[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global monitor

    # Startup
    print("Starting application...")
    monitor = RealtimeMonitor()
    await monitor.initialize()

    # Start monitoring in background
    asyncio.create_task(monitor.start_monitoring())

    yield

    # Shutdown
    print("Shutting down application...")
    if monitor:
        await monitor.close()


# Create FastAPI app
app = FastAPI(
    title="Volume Accumulation Dashboard",
    description="Real-time crypto volume anomaly detection",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Serve the dashboard."""
    return FileResponse("vol_accum_dashboard/dashboard/index.html")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "monitor_running": monitor is not None and monitor.running,
    }


@app.get("/api/alerts")
async def get_alerts():
    """Get current volume alerts."""
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    alerts = await monitor.get_current_alerts()
    return {
        "timestamp": datetime.now().isoformat(),
        "alerts": alerts,
    }


@app.get("/api/top-tokens")
async def get_top_tokens(limit: int = 50, sort_by: str = "spike_ratio", timeframe: int = 30):
    """
    Get top tokens sorted by spike ratio or volume.

    Args:
        limit: Number of top tokens to return (default: 50)
        sort_by: Sort by 'spike_ratio' or 'volume' (default: 'spike_ratio')
        timeframe: Days for average calculation when using spike_ratio (default: 30)
    """
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    if sort_by == "spike_ratio":
        tokens = await monitor.get_top_tokens_by_spike_ratio(top_n=limit, timeframe_days=timeframe)
    else:
        tokens = await monitor.get_top_tokens(top_n=limit)

    return {
        "timestamp": datetime.now().isoformat(),
        "window_start": monitor.window_start_time.isoformat(),
        "tokens": tokens,
        "sort_by": sort_by,
        "timeframe_days": timeframe if sort_by == "spike_ratio" else None,
    }


@app.get("/api/top-tokens-chart")
async def get_top_tokens_chart(limit: int = 10, timeframe: int = 30):
    """
    Get top tokens with exchange breakdown for chart visualization.

    Args:
        limit: Number of top tokens to return (default: 10)
        timeframe: Days for average calculation (default: 30)
    """
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    tokens = await monitor.get_top_tokens_by_spike_ratio(top_n=limit, timeframe_days=timeframe)

    # Format for chart
    chart_data = {
        "labels": [t["symbol"] for t in tokens],
        "tokens": [],
    }

    for token in tokens:
        chart_data["tokens"].append({
            "symbol": token["symbol"],
            "spike_ratio": token["spike_ratio"],
            "volume_15min": token["volume_15min"],
            "avg_daily_volume": token.get("avg_daily_volume", 0),
            "exchanges": token["exchanges"],
        })

    return {
        "timestamp": datetime.now().isoformat(),
        "chart_data": chart_data,
    }


@app.get("/api/token/{token_id}")
async def get_token_details(token_id: str):
    """Get detailed information for a specific token."""
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    store = JSONStore()

    # Load token metadata
    registry = await store.load_token_registry()
    if token_id not in registry:
        raise HTTPException(status_code=404, detail="Token not found")

    metadata = registry[token_id]

    # Get current volume
    current_volume = monitor.anomaly_detector.current_volumes.get(token_id, 0)
    exchanges = monitor.anomaly_detector.exchange_volumes.get(token_id, {})

    # Get alert info
    alert = await monitor.anomaly_detector.detect_anomalies(token_id, min_severity="low")

    return {
        "token_id": token_id,
        "metadata": metadata.model_dump(),
        "current_volume_15min": current_volume,
        "exchanges": exchanges,
        "alert": alert.model_dump() if alert else None,
    }


@app.get("/api/stats")
async def get_stats():
    """Get monitoring statistics."""
    if not monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    return {
        "timestamp": datetime.now().isoformat(),
        "window_start": monitor.window_start_time.isoformat(),
        "monitored_tokens": len(monitor.monitored_tokens),
        "exchanges": list(monitor.exchanges.keys()),
        "active_tokens": len(monitor.anomaly_detector.current_volumes),
        "rate_limit_stats": monitor.rate_limiter.get_all_stats(),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.

    Sends:
    - alerts: Volume spike alerts
    - top_tokens: Top tokens sorted by spike ratio
    - top_tokens_chart: Chart data for top 10 tokens
    - ping: Keepalive messages
    """
    await websocket.accept()
    connected_clients.append(websocket)

    try:
        print(f"Client connected. Total clients: {len(connected_clients)}")

        # Send initial data
        await websocket.send_json({
            "type": "connected",
            "timestamp": datetime.now().isoformat(),
        })

        # Keep connection alive and send updates
        while True:
            try:
                # Send current alerts
                alerts = await monitor.get_current_alerts()
                await websocket.send_json({
                    "type": "alerts",
                    "data": alerts,
                    "timestamp": datetime.now().isoformat(),
                })

                # Send top tokens (sorted by spike ratio)
                top_tokens = await monitor.get_top_tokens_by_spike_ratio(top_n=50, timeframe_days=30)
                await websocket.send_json({
                    "type": "top_tokens",
                    "data": top_tokens,
                    "timestamp": datetime.now().isoformat(),
                })

                # Send chart data (top 10)
                chart_tokens = await monitor.get_top_tokens_by_spike_ratio(top_n=10, timeframe_days=30)
                chart_data = {
                    "labels": [t["symbol"] for t in chart_tokens],
                    "tokens": chart_tokens,
                }
                await websocket.send_json({
                    "type": "chart_data",
                    "data": chart_data,
                    "timestamp": datetime.now().isoformat(),
                })

                # Wait before next update
                await asyncio.sleep(WEBSOCKET_PING_INTERVAL)

                # Send ping to keep connection alive
                await websocket.send_json({
                    "type": "ping",
                    "timestamp": datetime.now().isoformat(),
                })

            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"Error in WebSocket loop: {e}")
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        print(f"Client disconnected. Total clients: {len(connected_clients)}")


async def broadcast_update(message: dict):
    """Broadcast a message to all connected WebSocket clients."""
    disconnected = []

    # Iterate over a copy to avoid "dictionary changed size during iteration" error
    for client in list(connected_clients):
        try:
            await client.send_json(message)
        except Exception:
            disconnected.append(client)

    # Remove disconnected clients
    for client in disconnected:
        if client in connected_clients:
            connected_clients.remove(client)


def main():
    """Run the server."""
    print(f"Starting Volume Accumulation Dashboard on {API_HOST}:{API_PORT}")
    uvicorn.run(
        "vol_accum_dashboard.api.server:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
