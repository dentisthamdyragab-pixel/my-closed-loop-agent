import asyncio
import websockets
import json
import psutil
import os

class ControlHub:
    """
    WebSocket-based dashboard for system telemetry and HITL interactions.
    Provides a real-time view of CPU, VRAM, RAM and the active execution tree.
    """
    def __init__(self, host="0.0.0.0", port=8765):
        self.host = host
        self.port = port
        self.connected_clients = set()

    async def get_telemetry(self):
        """Collects system resources."""
        # VRAM would use pynvml in production
        return {
            "cpu_percent": psutil.cpu_percent(),
            "ram_percent": psutil.virtual_memory().percent,
            "active_threads": len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else 0,
            "timestamp": os.times().elapsed # Simplified
        }

    async def handler(self, websocket, path):
        """Handles WebSocket connections."""
        self.connected_clients.add(websocket)
        try:
            while True:
                # Push telemetry every second
                telemetry = await self.get_telemetry()
                await websocket.send(json.dumps({
                    "type": "TELEMETRY",
                    "data": telemetry
                }))
                await asyncio.sleep(1)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.connected_clients.remove(websocket)

    async def run(self):
        """Starts the Control Hub server."""
        print(f"Control Hub starting on ws://{self.host}:{self.port}")
        async with websockets.serve(self.handler, self.host, self.port):
            await asyncio.Future() # Run forever

if __name__ == "__main__":
    hub = ControlHub()
    try:
        asyncio.run(hub.run())
    except KeyboardInterrupt:
        print("Control Hub stopped.")
