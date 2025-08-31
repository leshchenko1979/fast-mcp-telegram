import traceback

from loguru import logger
from telethon import TelegramClient

from ..config.logging import format_diagnostic_info
from ..config.settings import API_HASH, API_ID, SESSION_PATH

_singleton_client = None


async def get_client() -> TelegramClient:
    global _singleton_client
    if _singleton_client is None:
        try:
            client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
            await client.connect()
            if not await client.is_user_authorized():
                logger.error(
                    "Session not authorized. Please run setup_telegram.py first"
                )
                raise Exception("Session not authorized")
            _singleton_client = client
        except Exception as e:
            logger.error(
                "Failed to create Telegram client",
                extra={
                    "diagnostic_info": format_diagnostic_info(
                        {
                            "error": {
                                "type": type(e).__name__,
                                "message": str(e),
                                "traceback": traceback.format_exc(),
                            },
                            "config": {
                                "session_path": str(SESSION_PATH),
                                "api_id_set": bool(API_ID),
                                "api_hash_set": bool(API_HASH),
                            },
                        }
                    )
                },
            )
            raise
    return _singleton_client


async def get_connected_client() -> TelegramClient:
    """
    Get a connected Telegram client, ensuring the connection is established.

    Returns:
        Connected TelegramClient instance

    Raises:
        Exception: If connection cannot be established
    """
    client = await get_client()
    if not await ensure_connection(client):
        raise Exception("Failed to establish connection to Telegram")
    return client


async def ensure_connection(client: TelegramClient) -> bool:
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
            extra={
                "diagnostic_info": format_diagnostic_info(
                    {
                        "error": {
                            "type": type(e).__name__,
                            "message": str(e),
                            "traceback": traceback.format_exc(),
                        }
                    }
                )
            },
        )
        return False


async def cleanup_client():
    global _singleton_client
    if _singleton_client is not None:
        try:
            await _singleton_client.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting client: {e}")
        _singleton_client = None
