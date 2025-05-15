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
