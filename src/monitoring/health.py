from loguru import logger
import asyncio
import traceback
from ..client.connection import connection_pool
from ..config.logging import format_diagnostic_info

async def connection_monitor():
    """Monitor Telegram connection pool status and attempt reconnection if needed."""
    while True:
        try:
            async with connection_pool._lock:
                pool_stats = {
                    "total_connections": len(connection_pool.pool),
                    "active_connections": sum(1 for v in connection_pool.in_use.values() if v),
                    "available_connections": sum(1 for v in connection_pool.in_use.values() if not v)
                }

                # Check each connection in the pool
                for i, client in enumerate(connection_pool.pool):
                    try:
                        if not client.is_connected():
                            logger.warning(f"Connection {i} lost, attempting to reconnect...")
                            try:
                                await client.connect()
                                if await client.is_user_authorized():
                                    logger.info(f"Successfully reconnected client {i}")
                                else:
                                    logger.error(f"Client {i} reconnected but not authorized")
                                    # Remove unauthorized client from pool
                                    connection_pool.pool.remove(client)
                                    if client in connection_pool.in_use:
                                        del connection_pool.in_use[client]
                            except Exception as e:
                                logger.error(f"Failed to reconnect client {i}: {e}")
                                logger.error(f"Exception details: {traceback.format_exc()}")
                                # Remove failed client from pool
                                connection_pool.pool.remove(client)
                                if client in connection_pool.in_use:
                                    del connection_pool.in_use[client]
                        else:
                            logger.debug(f"Client {i} connection status: Connected")
                    except Exception as e:
                        logger.error(f"Error checking client {i}: {e}")
                        logger.error(f"Exception details: {traceback.format_exc()}")

                logger.info("Connection pool status", extra={"pool_stats": pool_stats})

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
