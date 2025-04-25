#!/usr/bin/env python
"""Simple test client for the MCP server"""

import asyncio
import traceback
import sys
from fastmcp import Client
from loguru import logger

async def test_client():
    """Test basic connection to MCP server"""
    logger.info("Testing connection to MCP server")

    try:
        logger.info("Creating client...")
        # Let the Client auto-detect the appropriate transport
        async with Client("http://localhost:8000") as client:
            try:
                logger.info("Pinging server...")
                await client.ping()
                logger.info("Ping succeeded!")
            except Exception as e:
                logger.error(f"Ping failed: {e}")
                logger.error(f"Exception details: {traceback.format_exc()}")

            try:
                logger.info("Listing tools...")
                tools = await client.list_tools()
                logger.info(f"Available tools: {tools}")
            except Exception as e:
                logger.error(f"Error listing tools: {e}")
                logger.error(f"Exception details: {traceback.format_exc()}")

            # Test the hello tool from server.py
            logger.info("Testing 'hello' tool")
            try:
                result = await client.call_tool("hello", {"name": "Test Client"})
                logger.info(f"Hello tool result: {result}")
            except Exception as e:
                logger.error(f"Error calling 'hello' tool: {e}")
                logger.error(f"Exception details: {traceback.format_exc()}")

            # Test resource access
            logger.info("Testing 'server://info' resource")
            try:
                status = await client.read_resource("server://info")
                logger.info(f"Server status: {status}")
            except Exception as e:
                logger.error(f"Error accessing 'server://info' resource: {e}")
                logger.error(f"Exception details: {traceback.format_exc()}")
    except Exception as e:
        logger.error(f"Connection error: {e}")
        logger.error(f"Exception details: {traceback.format_exc()}")

    logger.info("Test client completed")

if __name__ == "__main__":
    # Configure console logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )

    # Run the test client
    asyncio.run(test_client())
