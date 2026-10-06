"""No-op store used when no durable backend is configured."""

from __future__ import annotations

from typing import Any, Iterable


class NullStateStore:
    enabled = False

    def save_task(self, task: dict[str, Any]) -> None:
        return None

    def load_task(self, task_id: str) -> dict[str, Any] | None:
        return None

    def list_tasks(
        self, *, statuses: Iterable[str] | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        return []

    def record_step(self, *args: Any, **kwargs: Any) -> None:
        return None

    def list_steps(self, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        return []

    def flush(self, timeout: float = 10.0) -> bool:
        return True
