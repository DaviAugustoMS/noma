"""Durable store for pipeline state: tasks and per-step checkpoints.

The store is a *mirror*: the in-memory ``TaskManager`` and the on-disk project
files stay the source the running app decides from. A store failure must never
break the pipeline, so implementations used by the app are wrapped in
``BufferedStateStore`` (write-behind, never raises).
"""

from __future__ import annotations

from typing import Any, Iterable, Protocol, runtime_checkable

# Step statuses.
STEP_STARTED = "started"
STEP_COMPLETED = "completed"
STEP_FAILED = "failed"
STEP_SKIPPED = "skipped"

TERMINAL_TASK_STATUSES = frozenset({"completed", "failed"})
ACTIVE_TASK_STATUSES = frozenset({"pending", "processing"})


class StateStoreError(Exception):
    """A state-store backend could not complete an operation."""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


@runtime_checkable
class StateStore(Protocol):
    def save_task(self, task: dict[str, Any]) -> None:
        """Upsert a task by ``task_id`` (shape of ``Task.to_dict()``)."""

    def load_task(self, task_id: str) -> dict[str, Any] | None:
        ...

    def list_tasks(
        self, *, statuses: Iterable[str] | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        ...

    def record_step(
        self,
        entity_type: str,
        entity_id: str,
        step: str,
        status: str,
        *,
        seq: int = 0,
        payload: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Upsert one checkpoint, unique per (entity_type, entity_id, step)."""

    def list_steps(self, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        """Checkpoints of one entity ordered by ``seq``."""

    def flush(self, timeout: float = 10.0) -> bool:
        """Wait for pending writes. ``True`` when everything was delivered."""
