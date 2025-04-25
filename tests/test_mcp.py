#!/usr/bin/env python
"""
Simple test script to verify MCP server functionality.
Run this script to test if your MCP server is working correctly.
"""

import sys
import asyncio
from loguru import logger
import os
from datetime import datetime
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from mcp.types import TextContent
import subprocess
import time
import json

def setup_logging():
    """Configure test script logging"""
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    # Configure logging
    logger.remove()  # Remove default handler

    # Add file handler
    log_file = f"logs/mcp_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logger.add(
        log_file,
        level="DEBUG",
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>"
    )

    # Add console handler
    logger.add(
        sys.stderr,
        level="INFO",
        format="<level>{level: <8}</level> | <level>{message}</level>"
    )

    logger.info(f"Test log file: {log_file}")

async def test_greet(client):
    """Test the greet tool"""
    logger.info("Testing 'greet' tool")
    result = await client.call_tool("greet", {"message": "Hello, World!", "uppercase": True})
    logger.info(f"Greet tool result: {result}")
    assert not result.isError, "Tool call returned an error"
    assert len(result.content) == 1, "Expected exactly one content item"
    assert isinstance(result.content[0], TextContent), "Expected text content"
    assert result.content[0].text == "HELLO, WORLD!", "Greet tool returned unexpected result"
    return result

async def test_server_status(client):
    """Test server status resource."""
    print("Testing 'server://status' resource")
    result = await client.read_resource("server://status")
    print(f"Server status: {result}")

    # Resource responses have contents instead of content
    assert len(result.contents) == 1, "Expected exactly one content item"
    content = result.contents[0]

    # Parse the JSON text content
    status_data = json.loads(content.text)
    assert isinstance(status_data, dict), "Status should be a dictionary"
    assert "status" in status_data, "Status should have 'status' field"
    assert "uptime" in status_data, "Status should have 'uptime' field"
    assert "version" in status_data, "Status should have 'version' field"
    assert status_data["status"] == "running"
    assert isinstance(status_data["uptime"], (int, float))
    assert isinstance(status_data["version"], str)
    print("test_server_status passed successfully")

async def test_server_uptime(client):
    """Test server uptime resource."""
    print("Testing 'server://uptime' resource")
    result = await client.read_resource("server://uptime")
    print(f"Server uptime: {result}")

    # Resource responses have contents instead of content
    assert len(result.contents) == 1, "Expected exactly one content item"
    content = result.contents[0]

    # Parse the JSON text content
    uptime_data = json.loads(content.text)
    assert isinstance(uptime_data, dict), "Uptime should be a dictionary"
    assert "uptime" in uptime_data, "Uptime should have 'uptime' field"
    assert isinstance(uptime_data["uptime"], (int, float))
    print("test_server_uptime passed successfully")

async def test_mcp_server():
    """Test the MCP server functionality"""
    logger.info("Starting MCP server test")

    # Create server parameters
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["server.py"]
    )

    try:
        # Connect to server using stdio transport
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as client:
                # Initialize the client
                await client.initialize()

                # Test each function separately with proper error handling
                for test_func in [test_greet, test_server_status, test_server_uptime]:
                    try:
                        await test_func(client)
                        logger.info(f"{test_func.__name__} passed successfully")
                    except Exception as e:
                        logger.error(f"Error during {test_func.__name__}: {e}")
                        raise

    finally:
        logger.info("Test completed")

if __name__ == "__main__":
    setup_logging()
    logger.info("Starting MCP server test suite")
    asyncio.run(test_mcp_server())
    logger.info("Test suite completed")
