import threading
import time
from collections import deque


class FailureLimiter:
    """In-memory sliding-window counter of failed attempts.

    Single-process only. Replace with a shared store (e.g. Redis) before
    running more than one API worker/replica.
    """

    _MAX_KEYS = 10_000

    def __init__(self, limit: int, window_seconds: int) -> None:
        self._limit = limit
        self._window = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._events.setdefault(key, deque())
        while q and now - q[0] > self._window:
            q.popleft()
        if not q:
            self._events.pop(key, None)
        return q

    def retry_after(self, key: str) -> int:
        """Seconds until the key is allowed again; 0 if not blocked."""
        now = time.monotonic()
        with self._lock:
            q = self._prune(key, now)
            if len(q) >= self._limit:
                return max(1, int(self._window - (now - q[0])) + 1)
            return 0

    def register_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._events) >= self._MAX_KEYS and key not in self._events:
                for k in list(self._events):
                    self._prune(k, now)
                if len(self._events) >= self._MAX_KEYS:
                    return  # fail open on memory pressure rather than crash
            self._events.setdefault(key, deque()).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


login_by_account = FailureLimiter(limit=5, window_seconds=900)
login_by_ip = FailureLimiter(limit=30, window_seconds=900)
