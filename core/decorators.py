"""
Python decorators - teen flavours:
  @timed              -> simple wrapper
  @retry(times=3)     -> parameterised (decorator factory)
  @cached_for(60)     -> Django cache ke saath, memoisation
"""
from __future__ import annotations

import functools
import hashlib
import logging
import time
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

from django.core.cache import cache

logger = logging.getLogger("pulseboard")

P = ParamSpec("P")
R = TypeVar("R")


def timed(fn: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(fn)  # __name__/__doc__ preserve - warna debugging narak
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            ms = (time.perf_counter() - start) * 1000
            logger.info("%s took %.1fms", fn.__qualname__, ms)

    return wrapper


def retry(
    times: int = 3,
    delay: float = 0.1,
    backoff: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
):
    """Decorator factory - arguments leta hai, phir decorator return karta hai."""

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            wait = delay
            for attempt in range(1, times + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions:
                    if attempt == times:
                        raise
                    logger.warning("%s failed (try %d/%d)", fn.__qualname__, attempt, times)
                    time.sleep(wait)
                    wait *= backoff
            raise AssertionError("unreachable")

        return wrapper

    return decorator


def _key_for(fn: Callable, args: tuple, kwargs: dict) -> str:
    raw = f"{fn.__module__}.{fn.__qualname__}:{args!r}:{sorted(kwargs.items())!r}"
    return "memo:" + hashlib.md5(raw.encode()).hexdigest()


def cached_for(seconds: int, key_prefix: str | None = None):
    """
    functools.lru_cache process-local hota hai; ye Django cache use karta hai
    to multi-worker setup me bhi shared rahe (Redis backend ke saath).
    Har wrapped fn pe .invalidate(*args) milta hai.
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            key = (key_prefix or "") + _key_for(fn, args, kwargs)
            sentinel = object()
            hit: Any = cache.get(key, sentinel)
            if hit is not sentinel:
                return hit
            value = fn(*args, **kwargs)
            cache.set(key, value, seconds)
            return value

        def invalidate(*args: Any, **kwargs: Any) -> None:
            cache.delete((key_prefix or "") + _key_for(fn, args, kwargs))

        wrapper.invalidate = invalidate  # type: ignore[attr-defined]
        return wrapper

    return decorator
