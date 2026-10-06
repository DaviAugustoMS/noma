"""Zeep Orbit implementation of the state store.

Talks to the Orbit REST contract directly (``{base}/{app}/{table}/``) with
``httpx`` instead of the Python SDK: the SDK uses ``urlopen`` without a
timeout, which could hang a pipeline thread indefinitely.

Contract (from the app's OpenAPI): paths end with ``/``; lists return
``{data, count, limit, offset}``; ``POST`` supports ``on_conflict`` +
``conflict_columns`` for a native upsert; filters use ``column=op.value``
(``eq.``, ``in.`` ...). The app uses email/password login, so the backend
signs in as a service user (``POST auth/login``) and keeps the session alive
with ``POST auth/refresh``, falling back to a new login when the refresh token
is no longer valid. A static token (``ORBIT_API_TOKEN``) is still accepted as
a legacy fallback, but it cannot be renewed.

Tables (see README): ``tasks`` (unique ``task_id``) and ``steps`` (unique
``entity_type, entity_id, step``).
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

import httpx

from .base import StateStoreError

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_PAGE = 100
# After a failed login, wait before trying again so a wrong password or a rate
# limit is not hammered by every queued write.
_LOGIN_BACKOFF_SECONDS = 60.0


class OrbitHttp:
    """Minimal Orbit table client. Credentials and tokens are never logged."""

    def __init__(
        self,
        base_url: str,
        app: str,
        *,
        email: str = "",
        password: str = "",
        token: str = "",
        client: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not (base_url and app):
            raise ValueError("ORBIT_BASE_URL and ORBIT_APP are required")
        if not ((email and password) or token):
            raise ValueError(
                "Provide ORBIT_SERVICE_EMAIL and ORBIT_SERVICE_PASSWORD (or ORBIT_API_TOKEN)"
            )
        self._base = f"{base_url.rstrip('/')}/{app}"
        self._client = client or httpx.Client(timeout=_TIMEOUT)
        self._email = email
        self._password = password
        self._token: str | None = token or None
        self._refresh_token: str | None = None
        self._clock = clock
        self._login_blocked_until = 0.0
        self._auth_lock = threading.Lock()

    def __repr__(self) -> str:  # never expose credentials
        return f"OrbitHttp(base={self._base!r})"

    # -- authentication --------------------------------------------------
    def _auth_post(self, path: str, body: dict[str, str]) -> dict[str, Any] | None:
        try:
            response = self._client.post(f"{self._base}/{path}", json=body)
            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, dict) and data.get("token") else None
        except (httpx.HTTPError, ValueError):
            pass
        return None

    def _apply(self, tokens: dict[str, Any]) -> None:
        self._token = tokens["token"]
        self._refresh_token = tokens.get("refresh_token") or self._refresh_token

    def _login(self) -> bool:
        if not (self._email and self._password):
            return False
        if self._clock() < self._login_blocked_until:
            return False
        tokens = self._auth_post(
            "auth/login", {"email": self._email, "password": self._password}
        )
        if not tokens:
            self._login_blocked_until = self._clock() + _LOGIN_BACKOFF_SECONDS
            return False
        self._apply(tokens)
        return True

    def _ensure_token(self) -> str:
        if self._token:
            return self._token
        with self._auth_lock:
            if not self._token:
                self._login()
        if not self._token:
            raise StateStoreError("Orbit login failed", status=401)
        return self._token

    def _renew(self, rejected_token: str) -> bool:
        """Refresh the session, or sign in again. Tokens live in memory only."""

        with self._auth_lock:
            if self._token != rejected_token:
                return True  # another thread already renewed it
            if self._refresh_token:
                tokens = self._auth_post(
                    "auth/refresh", {"refresh_token": self._refresh_token}
                )
                if tokens:
                    self._apply(tokens)
                    return True
                self._refresh_token = None
            if self._login():
                return True
            if self._email and self._password:
                self._token = None  # unusable and not renewable until login works
            return False

    # -- requests ---------------------------------------------------------
    def _send(
        self, method: str, path: str, params: dict[str, str] | None, json: Any
    ) -> tuple[httpx.Response, str]:
        token = self._ensure_token()
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

    def _request(
        self, method: str, path: str, *, params: dict[str, str] | None = None,
        json: Any = None,
    ) -> Any:
        response, used_token = self._send(method, path, params, json)
        if response.status_code == 401 and self._renew(used_token):
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
