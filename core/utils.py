"""Generators, itertools aur ek descriptor."""
from __future__ import annotations

import itertools
from collections.abc import Callable, Iterable, Iterator
from datetime import date, timedelta
from typing import Any, TypeVar

T = TypeVar("T")


def chunked(iterable: Iterable[T], size: int) -> Iterator[list[T]]:
    """
    Lazy chunking - 5 lakh rows bhi memory me nahi aayenge.
    bulk_create(batch_size=) ke saath pair karo.
    """
    iterator = iter(iterable)
    while chunk := list(itertools.islice(iterator, size)):
        yield chunk


def daterange(start: date, end: date) -> Iterator[date]:
    """Inclusive date generator - report me missing days fill karne ke liye."""
    for offset in range((end - start).days + 1):
        yield start + timedelta(days=offset)


def running_total(values: Iterable[int]) -> Iterator[int]:
    return itertools.accumulate(values)


class classproperty:
    """
    Descriptor - property ka class-level version.
    __get__ implement karke Python ka attribute lookup hijack kar rahe hain.
    """

    def __init__(self, fget: Callable[[type], Any]):
        self.fget = fget

    def __get__(self, obj: Any, owner: type | None = None) -> Any:
        return self.fget(owner if owner is not None else type(obj))
