"""Durable mirror of pipeline state (tasks and step checkpoints)."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from ...config import Config
from ...utils.logger import get_logger
from .base import (
    ACTIVE_TASK_STATUSES,
    STEP_COMPLETED,
    STEP_FAILED,
    STEP_SKIPPED,
    STEP_STARTED,
    TERMINAL_TASK_STATUSES,
    StateStore,
    StateStoreError,
)
from .null import NullStateStore

logger = get_logger("mirofish.state_store")

_lock = threading.Lock()
_store: StateStore | None = None


def is_state_store_configured() -> bool:
    has_login = bool(Config.ORBIT_SERVICE_EMAIL and Config.ORBIT_SERVICE_PASSWORD)
    return bool(Config.ORBIT_BASE_URL and (has_login or Config.ORBIT_API_TOKEN))


def get_state_store() -> StateStore:
    """Process-wide store: Orbit (buffered) when configured, otherwise a no-op."""

    global _store
    with _lock:
        if _store is None:
            if is_state_store_configured():
                from .buffered import BufferedStateStore
                from .orbit import OrbitHttp, OrbitStateStore

                _store = BufferedStateStore(
                    OrbitStateStore(
                        OrbitHttp(
                            Config.ORBIT_BASE_URL,
                            Config.ORBIT_APP,
                            email=Config.ORBIT_SERVICE_EMAIL,
                            password=Config.ORBIT_SERVICE_PASSWORD,
                            token=Config.ORBIT_API_TOKEN,
                        )
                    )
                )
                logger.info("Orbit state store enabled (app=%s)", Config.ORBIT_APP)
            else:
                _store = NullStateStore()
        return _store


def reset_state_store(store: StateStore | None = None) -> None:
    """Replace the process-wide store. Intended for tests and reconfiguration."""

    global _store
    with _lock:
        _store = store


def record_step(
    entity_type: str,
    entity_id: str,
    step: str,
    status: str,
    *,
    seq: int = 0,
    payload: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Checkpoint helper for pipeline code. Never raises."""

    try:
        get_state_store().record_step(
            entity_type, entity_id, step, status,
            seq=seq, payload=payload, error=error,
        )
    except Exception as error_:  # defensive: checkpoints are best effort
        logger.warning("checkpoint %s/%s not recorded: %s", entity_type, step,
                       type(error_).__name__)


def reconcile_orphan_tasks() -> int:
    """Mark tasks left active by a previous process as failed (interrupted).

    Runs once at startup. The in-memory ``TaskManager`` is empty at that point,
    so any task still ``pending``/``processing`` in the store has no worker.
    Returns how many tasks were closed.
    """

    store = get_state_store()
    grace = max(0, Config.ORBIT_ORPHAN_GRACE_SECONDS)
    now = datetime.now(timezone.utc)

    def is_stale(task: dict[str, Any]) -> bool:
        if not grace:
            return True
        try:
            updated = datetime.fromisoformat(str(task.get("updated_at")))
        except ValueError:
            return True
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        return (now - updated).total_seconds() >= grace

    orphans = [
        task
        for task in store.list_tasks(statuses=ACTIVE_TASK_STATUSES, limit=500)
        if is_stale(task)
    ]
    for task in orphans:
        task["status"] = "failed"
        task["error"] = task.get("error") or "Interrupted: backend restarted"
        store.save_task(task)
    if orphans:
        logger.warning("Marked %d orphan task(s) as interrupted", len(orphans))
    return len(orphans)


__all__ = [
    "ACTIVE_TASK_STATUSES",
    "STEP_COMPLETED",
    "STEP_FAILED",
    "STEP_SKIPPED",
    "STEP_STARTED",
    "StateStore",
    "StateStoreError",
    "TERMINAL_TASK_STATUSES",
    "get_state_store",
    "is_state_store_configured",
    "reconcile_orphan_tasks",
    "record_step",
    "reset_state_store",
]
