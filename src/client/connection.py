from typing import Dict, List, Optional
from telethon import TelegramClient
from loguru import logger
import asyncio
from asyncio import Lock, Semaphore
import traceback
from ..config.settings import (
    API_ID, API_HASH, SESSION_PATH,
    MAX_CONCURRENT_CONNECTIONS
)
from ..config.logging import format_diagnostic_info

class TelegramConnectionPool:
    def __init__(self, max_size: int = MAX_CONCURRENT_CONNECTIONS):
        self.max_size = max_size
        self.pool: List[TelegramClient] = []
        self.in_use: Dict[TelegramClient, bool] = {}
        self._lock = Lock()
        self._current_client = None

    async def __aenter__(self):
        """Async context manager entry."""
        client = await self.acquire()
        self._current_client = client
        return client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if exc_type is not None:
            logger.error(f"Error in connection context: {exc_val}")
        if self._current_client:
            await self.release(self._current_client)
            self._current_client = None

    async def acquire(self) -> TelegramClient:
        """Get a connection from the pool or create a new one."""
        async with self._lock:
            # Look for available connection
            for client in self.pool:
                if not self.in_use.get(client):
                    self.in_use[client] = True
                    return client

            # Create new connection if pool not full
            if len(self.pool) < self.max_size:
                client = await create_client()
                self.pool.append(client)
                self.in_use[client] = True
                return client

            # Wait for available connection if pool is full
            while True:
                for client in self.pool:
                    if not self.in_use.get(client):
                        self.in_use[client] = True
                        return client
                await asyncio.sleep(0.1)

    async def release(self, client: TelegramClient):
        """Return a connection to the pool."""
        async with self._lock:
            if client in self.in_use:
                self.in_use[client] = False

    async def cleanup(self):
        """Close all connections in the pool."""
        async with self._lock:
            for client in self.pool:
                try:
                    await client.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting client: {e}")
            self.pool.clear()
            self.in_use.clear()
            self._current_client = None

async def create_client() -> TelegramClient:
    """Create and connect a new Telegram client."""
    logger.debug("Creating new Telegram client")
    try:
        client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            logger.error("Session not authorized. Please run setup_telegram.py first")
            raise Exception("Session not authorized")

        return client
    except Exception as e:
        logger.error(
            "Failed to create Telegram client",
            extra={"diagnostic_info": format_diagnostic_info({
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc()
                },
                "config": {
                    "session_path": str(SESSION_PATH),
                    "api_id_set": bool(API_ID),
                    "api_hash_set": bool(API_HASH)
                }
            })}
        )
        raise

async def ensure_connection(client: TelegramClient) -> bool:
    """Ensure client is connected and try to reconnect if needed."""
    try:
        if not client.is_connected():
            logger.warning("Client disconnected, attempting to reconnect...")
            await client.connect()

            if not await client.is_user_authorized():
                logger.error("Client reconnected but not authorized")
                return False

            logger.info("Successfully reconnected client")

        return client.is_connected()

    except Exception as e:
        logger.error(
            f"Error ensuring connection: {e}",
            extra={"diagnostic_info": format_diagnostic_info({
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }
            })}
        )
        return False

# Global connection pool and semaphore
connection_pool = TelegramConnectionPool()
connection_semaphore = Semaphore(MAX_CONCURRENT_CONNECTIONS)
