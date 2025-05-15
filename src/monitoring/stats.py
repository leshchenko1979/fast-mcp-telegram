from typing import Dict, Any
from datetime import datetime
import time
import psutil
import json
from loguru import logger
import asyncio
from ..client.connection import get_client

class UsageStats:
    def __init__(self):
        self.start_time = time.time()

    async def get_basic_stats(self) -> Dict[str, Any]:
        """Get basic server statistics."""
        return {
            "uptime_hours": round((time.time() - self.start_time) / 3600, 2),
            "memory_mb": round(psutil.Process().memory_info().rss / 1024 / 1024, 2),
            "cpu_percent": round(psutil.Process().cpu_percent(), 2),
            "timestamp": datetime.now().isoformat()
        }

    async def get_telegram_stats(self, client) -> Dict[str, Any]:
        """Get Telegram-specific statistics."""
        try:
            if client and client.is_connected():
                me = await client.get_me()
                dialogs = await client.get_dialogs()
                return {
                    "telegram_user": f"{me.first_name} {me.last_name if me.last_name else ''} (@{me.username})",
                    "num_chats": len(dialogs),
                    "is_connected": True
                }
        except Exception as e:
            logger.warning(f"Error getting Telegram stats: {e}")

        return {
            "telegram_user": None,
            "num_chats": 0,
            "is_connected": False
        }

    async def get_full_stats(self) -> Dict[str, Any]:
        """Get comprehensive server statistics."""
        stats = await self.get_basic_stats()
        client = await get_client()
        telegram_stats = await self.get_telegram_stats(client)
        return {
            **stats,
            "telegram": telegram_stats
        }

async def log_usage_statistics():
    """Periodically log server usage statistics."""
    stats_collector = UsageStats()

    while True:
        try:
            stats = await stats_collector.get_full_stats()
            logger.info(f"Server stats: {json.dumps(stats, indent=2)}")
        except Exception as e:
            logger.error(f"Error logging usage statistics: {e}")

        await asyncio.sleep(300)  # Log every 5 minutes
