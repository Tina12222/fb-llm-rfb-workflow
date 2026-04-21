from __future__ import annotations

from functools import wraps
from typing import Any, Callable


def returns_keys(**_expected_types: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Compatibility decorator used by legacy utilities.

    It keeps original call behavior and can be extended later for runtime checks.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        return wrapper

    return decorator
