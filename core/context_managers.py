"""
Context managers - dono style:
  class-based (__enter__/__exit__)  -> state rakhna ho toh
  @contextmanager generator          -> chhote setup/teardown ke liye
"""
from __future__ import annotations

import time
from contextlib import contextmanager

from django.db import connection, reset_queries


class CaptureQueries:
    """
    with CaptureQueries() as q:
        list(Project.objects.all())
    print(q.count, q.duplicates())

    N+1 pakadne ka sabse seedha tarika. DEBUG=True chahiye.
    """

    def __init__(self, label: str = "block"):
        self.label = label
        self.queries: list[dict] = []
        self.ms: float = 0.0

    def __enter__(self) -> CaptureQueries:
        reset_queries()
        self._start = time.perf_counter()
        self._offset = len(connection.queries)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.ms = (time.perf_counter() - self._start) * 1000
        self.queries = connection.queries[self._offset :]
        return False  # exception ko suppress mat karo

    @property
    def count(self) -> int:
        return len(self.queries)

    def duplicates(self) -> dict[str, int]:
        seen: dict[str, int] = {}
        for q in self.queries:
            seen[q["sql"]] = seen.get(q["sql"], 0) + 1
        return {sql: n for sql, n in seen.items() if n > 1}


@contextmanager
def stopwatch(label: str, enabled: bool = True):
    start = time.perf_counter()
    try:
        yield
    finally:
        if enabled:
            print(f"[{label}] {(time.perf_counter() - start) * 1000:.1f}ms")
