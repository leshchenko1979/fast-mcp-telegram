from typing import Dict, Any
from loguru import logger
import traceback
from importlib import import_module
from ..client.connection import get_connected_client

async def invoke_mtproto_method(method_full_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dynamically invoke any MTProto method by name and parameters.

    Args:
        method_full_name: Full class name of the MTProto method, e.g., 'messages.GetHistory'
        params: Dictionary of parameters for the method
    Returns:
        Result of the method call as a dict, or error info
    """
    request_id = f"mtproto_{method_full_name}_{params.get('peer', '')}"
    logger.debug(f"[{request_id}] Invoking MTProto method: {method_full_name} with params: {params}")
    try:
        # Parse method_full_name
        if '.' not in method_full_name:
            raise ValueError("method_full_name must be in the form 'module.ClassName', e.g., 'messages.GetHistory'")
        module_name, class_name = method_full_name.rsplit('.', 1)
        # Telethon uses e.g. GetHistoryRequest, not GetHistory
        if not class_name.endswith('Request'):
            class_name += 'Request'
        tl_module = import_module(f"telethon.tl.functions.{module_name}")
        method_cls = getattr(tl_module, class_name)
        method_obj = method_cls(**params)
        client = await get_connected_client()
        result = await client(method_obj)
        # Try to convert result to dict (if possible)
        if hasattr(result, 'to_dict'):
            result_dict = result.to_dict()
        else:
            result_dict = str(result)
        logger.info(f"[{request_id}] MTProto method {method_full_name} invoked successfully")
        return {"ok": True, "result": result_dict}
    except Exception as e:
        error_info = {
            "request_id": request_id,
            "error": {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc()
            },
            "method_full_name": method_full_name,
            "params": params
        }
        logger.error(f"[{request_id}] Error invoking MTProto method", extra={"diagnostic_info": error_info})
        return {"ok": False, "error": error_info}
