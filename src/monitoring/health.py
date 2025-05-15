from loguru import logger
import asyncio
import traceback
from ..client.connection import get_client
from ..config.logging import format_diagnostic_info

async def connection_monitor():
    """Monitor Telegram client status and attempt reconnection if needed."""
    while True:
        try:
            client = await get_client()
            if not await client.is_connected():
                logger.warning("Client disconnected, attempting to reconnect...")
                await client.connect()
                if await client.is_user_authorized():
                    logger.info("Successfully reconnected client")
                else:
                    logger.error("Client reconnected but not authorized")
            else:
                logger.debug("Client connection status: Connected")
        except Exception as e:
            logger.error(
                f"Error in connection monitor: {e}",
                extra={"diagnostic_info": format_diagnostic_info({
                    "error": {
                        "type": type(e).__name__,
                        "message": str(e),
                        "traceback": traceback.format_exc()
                    }
                })}
            )
        await asyncio.sleep(30)  # Check every 30 seconds
