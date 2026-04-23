#!/usr/bin/env python3
"""Integration test for get_messages via MCP Client (higher order function).

Run with: uv run python3 tests/integration/test_get_messages_timing.py
"""
import asyncio
import signal
import subprocess
import sys
import time
from datetime import datetime
import json

sys.path.insert(0, "/Users/leshchenko/coding_projects/vds/deployed_projects/fast-mcp-telegram")

from fastmcp import Client
from fastmcp.client.transports.stdio import StdioTransport


async def main():
    server_path = "/Users/leshchenko/coding_projects/vds/deployed_projects/fast-mcp-telegram/src/server.py"

    # Start server process
    proc = subprocess.Popen(
        [sys.executable, server_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd="/Users/leshchenko/coding_projects/vds/deployed_projects/fast-mcp-telegram",
    )

    await asyncio.sleep(2)

    try:
        print("Connecting to server via stdio...")
        transport = StdioTransport(
            command=sys.executable,
            args=[server_path],
            cwd="/Users/leshchenko/coding_projects/vds/deployed_projects/fast-mcp-telegram",
        )
        mcp = Client(transport)

        async with mcp:
            # Test get_messages directly with known chat_id
            print("\n--- Testing get_messages with min_date ---")
            chat_id = "2151717006"  # "Финансы — ОД" group
            since = "2026-04-16"
            limit = 1000

            print(f"Calling get_messages with chat_id={chat_id}, min_date={since}, limit={limit}")
            start = time.time()
            print(f"Starting at {datetime.now().isoformat()}")

            result = await mcp.call_tool(
                "get_messages",
                {"chat_id": chat_id, "min_date": since, "limit": limit},
            )
            elapsed = time.time() - start

            print(f"\nCompleted in {elapsed:.2f}s")
            print(f"Result type: {type(result)}")

            content = result.content[0].text
            resp_data = json.loads(content)
            print(f"Keys: {list(resp_data.keys())}")

            if "messages" in resp_data:
                msgs = resp_data["messages"]
                print(f"Messages count: {len(msgs)}")
                if msgs:
                    print(f"First: [{msgs[0].get('id')}] {msgs[0].get('date')}")
                    print(f"Last: [{msgs[-1].get('id')}] {msgs[-1].get('date')}")
            if "error" in resp_data:
                print(f"ERROR: {resp_data['error']}")

    finally:
        proc.terminate()
        proc.wait(timeout=5)

    print(f"\n{'='*60}")
    print("MCP timing test completed")
    print('='*60)


if __name__ == "__main__":
    def timeout_handler(signum, frame):
        print("\n[TIMEOUT] Test exceeded 30 seconds, exiting...")
        sys.exit(1)

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(30)

    asyncio.run(main())