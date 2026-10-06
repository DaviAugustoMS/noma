"""Zeep Orbit implementation of the state store.

Talks to the Orbit REST contract directly (``{base}/{app}/{table}/``) with
``httpx`` instead of the Python SDK: the SDK uses ``urlopen`` without a
timeout, which could hang a pipeline thread indefinitely.

Contract (from the app's OpenAPI): paths end with ``/``; lists return
``{data, count, limit, offset}``; ``POST`` supports ``on_conflict`` +
``conflict_columns`` for a native upsert; filters use ``column=op.value``
(``eq.``, ``in.`` ...); app tokens expire and are renewed through
``POST auth/token/refresh``.

Tables (see README): ``tasks`` (unique ``task_id``) and ``steps`` (unique
``entity_type, entity_id, step``).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import threading

import httpx

from .base import StateStoreError

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_PAGE = 100


class OrbitHttp:
    """Minimal Orbit table client. The token is never logged or put in errors."""

    def __init__(
        self,
        base_url: str,
        app: str,
        token: str,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        if not (base_url and app and token):
            raise ValueError("ORBIT_BASE_URL, ORBIT_APP and ORBIT_API_TOKEN are required")
        self._base = f"{base_url.rstrip('/')}/{app}"
        self._client = client or httpx.Client(timeout=_TIMEOUT)
        self._token = token
        self._refresh_lock = threading.Lock()

    def __repr__(self) -> str:  # never expose the token
        return f"OrbitHttp(base={self._base!r})"

    def _send(
        self, method: str, path: str, params: dict[str, str] | None, json: Any
    ) -> tuple[httpx.Response, str]:
        token = self._token
        try:
            response = self._client.request(
                method,
                f"{self._base}/{path}",
                params=params,
                json=json,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as error:
            raise StateStoreError(f"Orbit transport error: {type(error).__name__}") from error
        return response, token

    def _refresh(self, rejected_token: str) -> bool:
        """Reissue the app token once. Kept in memory only (never persisted)."""

        with self._refresh_lock:
            if self._token != rejected_token:
                return True  # another thread already renewed it
            try:
                response = self._client.post(
                    f"{self._base}/auth/token/refresh",
                    headers={"Authorization": f"Bearer {rejected_token}"},
                )
                new_token = response.json().get("token") if response.status_code == 200 else None
            except (httpx.HTTPError, ValueError):
                return False
            if not new_token:
                return False
            self._token = new_token
            return True

    def _request(
        self, method: str, path: str, *, params: dict[str, str] | None = None,
        json: Any = None,
    ) -> Any:
        response, used_token = self._send(method, path, params, json)
        if response.status_code == 401 and self._refresh(used_token):
            response, _ = self._send(method, path, params, json)
        if response.status_code == 204:
            return None
        if response.status_code >= 400:
            raise StateStoreError(
                f"Orbit {method} {path} failed with HTTP {response.status_code}",
                status=response.status_code,
            )
        try:
            return response.json()
        except ValueError as error:
            raise StateStoreError("Orbit returned a non-JSON response") from error

    def list(
        self, table: str, *, filters: dict[str, str] | None = None,
        order: str | None = None, limit: int = _PAGE, offset: int = 0,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {"limit": str(limit)}
        if offset:
            params["offset"] = str(offset)
        if order:
            params["order"] = order
        params.update(filters or {})
        body = self._request("GET", f"{table}/", params=params)
        return list((body or {}).get("data") or [])

    def upsert(
        self, table: str, conflict_columns: list[str], data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Insert, or update the row matching the unique ``conflict_columns``."""

        return self._request(
            "POST",
            f"{table}/",
            json={**data, "on_conflict": "update", "conflict_columns": conflict_columns},
        )


def _iso(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.astimezone()
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


class OrbitStateStore:
    enabled = True

    def __init__(self, http: OrbitHttp) -> None:
        self._http = http

    @staticmethod
    def _clean(row: dict[str, Any]) -> dict[str, Any]:
        """Drop ``None``: the schema declares non-nullable strings/objects."""

        return {key: value for key, value in row.items() if value is not None}

    # -- tasks ----------------------------------------------------------
    def save_task(self, task: dict[str, Any]) -> None:
        metadata = task.get("metadata") or {}
        row = {
            "task_id": task["task_id"],
            "task_type": task.get("task_type") or "",
            "status": task.get("status") or "pending",
            "progress": int(task.get("progress") or 0),
            "message": task.get("message") or "",
            "result": task.get("result"),
            "error": task.get("error"),
            "metadata": metadata,
            "progress_detail": task.get("progress_detail") or {},
            "project_id": metadata.get("project_id"),
            "task_created_at": _iso(task.get("created_at")),
            "task_updated_at": _iso(task.get("updated_at")),
        }
        self._http.upsert("tasks", ["task_id"], self._clean(row))

    @staticmethod
    def _task_from_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "task_id": row.get("task_id"),
            "task_type": row.get("task_type"),
            "status": row.get("status"),
            "progress": row.get("progress") or 0,
            "message": row.get("message") or "",
            "result": row.get("result"),
            "error": row.get("error"),
            "metadata": row.get("metadata") or {},
            "progress_detail": row.get("progress_detail") or {},
            "created_at": row.get("task_created_at"),
            "updated_at": row.get("task_updated_at"),
        }

    def load_task(self, task_id: str) -> dict[str, Any] | None:
        rows = self._http.list("tasks", filters={"task_id": f"eq.{task_id}"}, limit=1)
        return self._task_from_row(rows[0]) if rows else None

    def list_tasks(
        self, *, statuses: Iterable[str] | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        filters = (
            {"status": "in." + ",".join(sorted(set(statuses)))}
            if statuses is not None
            else None
        )
        tasks: list[dict[str, Any]] = []
        offset = 0
        while len(tasks) < limit:
            rows = self._http.list(
                "tasks", filters=filters, order="task_updated_at.desc",
                limit=_PAGE, offset=offset,
            )
            tasks.extend(self._task_from_row(row) for row in rows)
            if len(rows) < _PAGE:
                break
            offset += _PAGE
        return tasks[:limit]

    # -- steps ----------------------------------------------------------
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
        now = _iso(datetime.now(timezone.utc))
        row: dict[str, Any] = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "step": step,
            "status": status,
            "seq": seq,
            "payload": payload or {},
            "error": error,
        }
        if status == "started":
            row["started_at"] = now
        else:
            row["finished_at"] = now
        self._http.upsert(
            "steps", ["entity_type", "entity_id", "step"], self._clean(row)
        )

    def list_steps(self, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        return self._http.list(
            "steps",
            filters={
                "entity_type": f"eq.{entity_type}",
                "entity_id": f"eq.{entity_id}",
            },
            order="seq.asc",
            limit=_PAGE,
        )

    def flush(self, timeout: float = 10.0) -> bool:
        return True
