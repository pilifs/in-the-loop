"""Measurement for sync.py: where one command's time goes (`sync.py perf`). Nothing here decides a
result, so the caches' fingerprints leave this file out (redactor.FINGERPRINTED)."""
from __future__ import annotations

import contextlib
import resource
import threading
import time
from collections import Counter
from datetime import datetime


def _child_cpu() -> float:
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


class Perf:
    """Where one command's time goes: wall time, its own CPU time and its subprocesses', per phase
    (nested phases are named by path, a/b), and counters of bytes, cache hits, subprocesses and
    network requests. Every command appends one record to PERF_LOG; LLM_TRACES_PERF=1 prints it
    too. Holds names and numbers only, no paths or content. Threads may count and time phases:
    each has its own nesting, and CPU time is the process's, so phases that overlap in time
    share it."""

    def __init__(self) -> None:
        self.wall, self.cpu, self.child = time.perf_counter(), time.process_time(), _child_cpu()
        self.phases: dict[str, list[float]] = {}  # path -> [calls, wall, cpu, child cpu]
        self.counters: Counter = Counter()
        self._local = threading.local()  # .stack: the phases this thread is in
        self._lock = threading.Lock()

    @contextlib.contextmanager
    def phase(self, name: str):
        stack = self._local.__dict__.setdefault("stack", [])
        stack.append(name)
        path = "/".join(stack)
        wall, cpu, child = time.perf_counter(), time.process_time(), _child_cpu()
        try:
            yield
        finally:
            stack.pop()
            with self._lock:
                row = self.phases.setdefault(path, [0, 0.0, 0.0, 0.0])
                row[0] += 1
                row[1] += time.perf_counter() - wall
                row[2] += time.process_time() - cpu
                row[3] += _child_cpu() - child

    def count(self, key: str, n: float = 1) -> None:
        with self._lock:
            self.counters[key] += n

    def record(self, command: str) -> dict:
        r3 = lambda x: round(x, 3)
        return {"command": command, "at": datetime.now().isoformat(timespec="seconds"),
                "wall": r3(time.perf_counter() - self.wall), "cpu": r3(time.process_time() - self.cpu),
                "child_cpu": r3(_child_cpu() - self.child),
                "phases": {k: {"calls": int(c), "wall": r3(w), "cpu": r3(u), "child_cpu": r3(ch)}
                           for k, (c, w, u, ch) in self.phases.items()},
                "counters": {k: r3(v) if isinstance(v, float) else v for k, v in sorted(self.counters.items())}}


perf = Perf()
