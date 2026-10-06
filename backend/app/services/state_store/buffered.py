"""Write-behind wrapper: durable mirroring that can never break the pipeline.

* ``save_task`` is coalesced per ``task_id`` (progress updates are frequent;
  only the latest state matters) and delivered in order by one worker thread.
* ``record_step`` is queued in order and never coalesced.
* Failures are retried with backoff, then logged (without payloads) and
  dropped; nothing is ever raised to the caller.
"""

from __future__ import annotations

import atexit
import threading
import time
from collections import deque
from typing import Any, Callable, Iterable

from ...utils.logger import get_logger
from .base import StateStore

logger = get_logger("mirofish.state_store")

_RETRY_DELAYS = (0.5, 2.0)  # attempts = len + 1


class BufferedStateStore:
    enabled = True

    def __init__(
        self,
        inner: StateStore,
        *,
        sleep: Callable[[float], None] = time.sleep,
        retry_delays: tuple[float, ...] = _RETRY_DELAYS,
    ) -> None:
        self._inner = inner
        self._sleep = sleep
        self._retry_delays = retry_delays
        self._cond = threading.Condition()
        # ("task", key) or ("step", op). Tasks are resolved at dequeue time so a
        # retry re-sends the same snapshot instead of losing it.
        self._queue: deque[tuple[str, Any]] = deque()
        self._pending_tasks: dict[str, dict[str, Any]] = {}
        self._in_flight = 0
        self._dropped = 0
        self._worker: threading.Thread | None = None
        atexit.register(self.flush, 5.0)

    # -- writes (never raise) -------------------------------------------
    def save_task(self, task: dict[str, Any]) -> None:
        key = f"task:{task.get('task_id')}"
        with self._cond:
            already_queued = key in self._pending_tasks
            self._pending_tasks[key] = dict(task)
            if not already_queued:
                self._queue.append(("task", key))
            self._ensure_worker()
            self._cond.notify_all()

    def record_step(self, *args: Any, **kwargs: Any) -> None:
        with self._cond:
            self._queue.append(
                ("step", lambda: self._inner.record_step(*args, **kwargs))
            )
            self._ensure_worker()
            self._cond.notify_all()

    # -- reads (best effort) --------------------------------------------
    def load_task(self, task_id: str) -> dict[str, Any] | None:
        try:
            return self._inner.load_task(task_id)
        except Exception as error:
            logger.warning("state store read failed: %s", type(error).__name__)
            return None

    def list_tasks(
        self, *, statuses: Iterable[str] | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        try:
            return self._inner.list_tasks(statuses=statuses, limit=limit)
        except Exception as error:
            logger.warning("state store read failed: %s", type(error).__name__)
            return []

    def list_steps(self, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        try:
            return self._inner.list_steps(entity_type, entity_id)
        except Exception as error:
            logger.warning("state store read failed: %s", type(error).__name__)
            return []

    # -- delivery --------------------------------------------------------
    def _ensure_worker(self) -> None:
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(
                target=self._run, name="StateStoreWriter", daemon=True
            )
            self._worker.start()

    def _run(self) -> None:
        while True:
            with self._cond:
                while not self._queue:
                    # Exit when idle so tests and short-lived processes do not
                    # leak threads; ``_ensure_worker`` restarts on demand.
                    if not self._cond.wait(timeout=5.0) and not self._queue:
                        self._worker = None
                        return
                kind, item = self._queue.popleft()
                if kind == "task":
                    task = self._pending_tasks.pop(item)
                    op = lambda task=task: self._inner.save_task(task)  # noqa: E731
                else:
                    op = item
                self._in_flight += 1
            try:
                self._deliver(op)
            finally:
                with self._cond:
                    self._in_flight -= 1
                    self._cond.notify_all()

    def _deliver(self, op: Callable[[], None]) -> None:
        for attempt in range(len(self._retry_delays) + 1):
            try:
                op()
                return
            except Exception as error:
                if attempt == len(self._retry_delays):
                    self._dropped += 1
                    logger.warning(
                        "state store write dropped after %d attempts: %s",
                        attempt + 1, type(error).__name__,
                    )
                    return
                self._sleep(self._retry_delays[attempt])

    def flush(self, timeout: float = 10.0) -> bool:
        deadline = time.monotonic() + timeout
        with self._cond:
            while self._queue or self._in_flight:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._cond.wait(timeout=remaining)
        return self._dropped == 0

    @property
    def dropped_writes(self) -> int:
        return self._dropped
