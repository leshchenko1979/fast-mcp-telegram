import inspect
from collections.abc import Callable
from functools import wraps

from src.utils.error_handling import handle_tool_error, log_and_build_error


def with_error_handling(operation_name: str):
    """Decorator to add consistent error handling to MCP tool functions.

    Mirrors behavior previously embedded in server module to keep DRY.
    Preserves original signature information for improved parameter logging.
    """

    def decorator(func: Callable) -> Callable:
        # Attempt to capture original signature even if decorated
        try:
            original_func = func
            if hasattr(func, "__wrapped__"):
                original_func = func.__wrapped__
            elif hasattr(func, "func") and callable(func.func):
                original_func = func.func
            original_sig = inspect.signature(original_func)
        except Exception:  # pragma: no cover - defensive
            original_sig = None

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build params dict from captured signature for better error context
            params = {}
            if original_sig:
                try:
                    bound_args = original_sig.bind(*args, **kwargs)
                    bound_args.apply_defaults()
                    params = dict(bound_args.arguments)
                except Exception:
                    param_names = list(original_sig.parameters.keys())
                    if param_names and param_names[0] == "self":
                        param_names = param_names[1:]
                    for i, arg in enumerate(args):
                        if i < len(param_names):
                            params[param_names[i]] = arg
                    params.update(kwargs)
            else:
                params = dict(kwargs)

            try:
                result = await func(*args, **kwargs)
                error_response = handle_tool_error(result, operation_name, params)
                if error_response:
                    return error_response
                return result
            except Exception as e:
                return log_and_build_error(
                    operation=operation_name,
                    error_message=f"Unexpected error: {e}",
                    params=params,
                    exception=e,
                )

        return wrapper

    return decorator
