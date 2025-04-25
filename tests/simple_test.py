#!/usr/bin/env python
"""Simple direct test script to check FastMCP server connectivity"""

import asyncio
import httpx

async def test_server():
    """Simple connectivity test"""
    print("Testing server connectivity...")

    try:
        # Test normal HTTP connection
        async with httpx.AsyncClient() as client:
            print("Testing HTTP connection to server...")
            resp = await client.get("http://localhost:8000")
            print(f"HTTP response: {resp.status_code}")
    except Exception as e:
        print(f"HTTP connection error: {e}")

    # Let's also try a websocket connection
    try:
        import websockets
        print("Testing WebSocket connection...")
        async with websockets.connect('ws://localhost:8000/ws') as websocket:
            print("WebSocket connection successful")
    except Exception as e:
        print(f"WebSocket connection error: {e}")

if __name__ == "__main__":
    asyncio.run(test_server())
