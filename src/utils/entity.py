from loguru import logger
from ..client.connection import get_client

async def get_entity_by_id(entity_id):
    """
    A wrapper around client.get_entity to handle numeric strings and log errors.
    """
    client = await get_client()
    peer = None
    try:
        # Try to convert entity_id to an integer if it's a numeric string
        try:
            peer = int(entity_id)
        except (ValueError, TypeError):
            peer = entity_id

        if not peer:
            raise ValueError("Entity ID cannot be null or empty")

        return await client.get_entity(peer)
    except Exception as e:
        logger.warning(f"Could not get entity for '{entity_id}' (parsed as '{peer}'). Error: {e}")
        return None

def build_entity_dict(entity) -> dict:
    if not entity:
        return None
    first_name = getattr(entity, 'first_name', None)
    last_name = getattr(entity, 'last_name', None)
    return {
        "id": getattr(entity, 'id', None),
        "title": getattr(entity, 'title', None),
        "type": entity.__class__.__name__ if hasattr(entity, '__class__') else None,
        "username": getattr(entity, 'username', None),
        "first_name": first_name,
        "last_name": last_name
    }
