"""State store: Orbit REST mirror, write-behind buffer and TaskManager wiring."""

import json
import threading

import httpx
import pytest

from app.config import Config
from app.models.task import TaskManager, TaskStatus
from app.services import state_store
from app.services.state_store.base import StateStoreError
from app.services.state_store.buffered import BufferedStateStore
from app.services.state_store.null import NullStateStore
from app.services.state_store.orbit import OrbitHttp, OrbitStateStore

TOKEN = "orbit-secret-token"


class FakeOrbit:
    """In-memory stand-in for the Orbit REST contract (see the app's OpenAPI)."""

    COLUMNS = {
        "tasks": {"task_id", "task_type", "status", "progress", "message", "result",
                  "error", "metadata", "progress_detail", "project_id",
                  "task_created_at", "task_updated_at"},
        "steps": {"entity_type", "entity_id", "step", "status", "seq", "payload",
                  "error", "started_at", "finished_at"},
    }

    def __init__(self):
        self.tables = {"tasks": [], "steps": []}
        self.valid_tokens = {TOKEN}
        self.refreshed_to = "orbit-renewed-token"
        self.requests = []
        self.fail_next = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        parts = request.url.path.strip("/").split("/")
        assert parts[0] == "mirofish"
        auth = request.headers["Authorization"].removeprefix("Bearer ")
        if parts[1:] == ["auth", "token", "refresh"]:
            if auth != TOKEN:
                return httpx.Response(401, json={"error": "unauthorized"})
            self.valid_tokens = {self.refreshed_to}
            return httpx.Response(200, json={"token": self.refreshed_to})
        if auth not in self.valid_tokens:
            return httpx.Response(401, json={"error": "unauthorized"})
        if self.fail_next:
            self.fail_next -= 1
            return httpx.Response(503, json={"error": "unavailable"})
        # The contract documents every path with a trailing slash.
        assert request.url.path.endswith("/"), request.url.path
        table = parts[1]
        rows = self.tables[table]
        if request.method == "GET":
            params = dict(request.url.params)
            limit = int(params.pop("limit", 100))
            offset = int(params.pop("offset", 0))
            order = params.pop("order", None)
            if set(params) - self.COLUMNS[table]:
                return httpx.Response(400, json={"error": "unknown column"})
            matched = [r for r in rows if all(self._match(r.get(k), v) for k, v in params.items())]
            if order:
                field, direction = order.split(".")
                matched.sort(key=lambda r: str(r.get(field) or ""), reverse=direction == "desc")
            return httpx.Response(200, json={
                "data": matched[offset:offset + limit],
                "count": len(matched), "limit": limit, "offset": offset,
            })
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body.pop("on_conflict") == "update"
        conflict = body.pop("conflict_columns")
        assert all(v is not None for v in body.values()), "None must be omitted"
        existing = next(
            (r for r in rows if all(r.get(c) == body.get(c) for c in conflict)), None
        )
        if existing:
            existing.update(body)
            return httpx.Response(200, json=existing)
        row = {"id": f"row-{len(rows) + 1}", **body}
        rows.append(row)
        return httpx.Response(201, json=row)

    @staticmethod
    def _match(value, expr):
        op, _, arg = expr.partition(".")
        if op == "eq":
            return value == arg
        if op == "in":
            return value in arg.split(",")
        raise AssertionError(f"operator {op}")


@pytest.fixture
def orbit():
    fake = FakeOrbit()
    http = OrbitHttp(
        "https://orbit.example", "mirofish", TOKEN,
        client=httpx.Client(transport=httpx.MockTransport(fake.handler)),
    )
    fake.store = OrbitStateStore(http)
    fake.http = http
    return fake


def _task(task_id="t1", status="processing", progress=10, **extra):
    return {
        "task_id": task_id, "task_type": "graph_build", "status": status,
        "progress": progress, "message": "m", "result": None, "error": None,
        "metadata": {"project_id": "proj_1"}, "progress_detail": {},
        "created_at": "2026-10-06T10:00:00", "updated_at": "2026-10-06T10:00:01",
        **extra,
    }


def test_save_task_upserts_by_task_id_and_maps_columns(orbit):
    orbit.store.save_task(_task(progress=10))
    orbit.store.save_task(_task(progress=60, status="completed"))

    assert len(orbit.tables["tasks"]) == 1
    row = orbit.tables["tasks"][0]
    assert row["progress"] == 60 and row["status"] == "completed"
    assert row["project_id"] == "proj_1"
    assert row["task_created_at"].startswith("2026-10-06")

    loaded = orbit.store.load_task("t1")
    assert loaded["status"] == "completed"
    assert loaded["created_at"] == row["task_created_at"]
    assert orbit.store.load_task("missing") is None


def test_record_step_is_unique_per_entity_step_and_keeps_start_time(orbit):
    store = orbit.store
    store.record_step("graph_build", "t1", "ingest", "started", seq=4)
    store.record_step("graph_build", "t1", "ingest", "completed", seq=4,
                      payload={"batch_id": "b1"})
    store.record_step("graph_build", "t1", "chunked", "completed", seq=1)

    assert len(orbit.tables["steps"]) == 2
    ingest = next(r for r in orbit.tables["steps"] if r["step"] == "ingest")
    assert ingest["status"] == "completed"
    assert ingest["started_at"] and ingest["finished_at"]
    assert [s["step"] for s in store.list_steps("graph_build", "t1")] == [
        "chunked", "ingest",
    ]


def test_save_task_uses_a_single_native_upsert_request(orbit):
    orbit.store.save_task(_task())
    [request] = orbit.requests
    body = json.loads(request.content)
    assert request.method == "POST" and request.url.path == "/mirofish/tasks/"
    assert body["on_conflict"] == "update"
    assert body["conflict_columns"] == ["task_id"]
    assert "error" not in body and "result" not in body  # None is omitted


def test_list_tasks_filters_status_on_the_server(orbit):
    for task_id, status in (("a", "processing"), ("b", "completed"), ("c", "pending")):
        orbit.store.save_task(_task(task_id, status=status))
    orbit.requests.clear()

    tasks = orbit.store.list_tasks(statuses={"pending", "processing"})
    assert sorted(t["task_id"] for t in tasks) == ["a", "c"]
    assert dict(orbit.requests[0].url.params)["status"] == "in.pending,processing"


def test_expired_token_is_refreshed_once_and_the_request_retried(orbit):
    orbit.valid_tokens = set()  # the configured token has expired
    orbit.valid_tokens.add("something-else")
    orbit.refreshed_to = "orbit-renewed-token"

    # Refresh needs the *current* token to be accepted by the refresh endpoint.
    orbit.store.save_task(_task())

    assert len(orbit.tables["tasks"]) == 1
    paths = [r.url.path for r in orbit.requests]
    assert paths == [
        "/mirofish/tasks/", "/mirofish/auth/token/refresh", "/mirofish/tasks/",
    ]
    assert orbit.requests[-1].headers["Authorization"] == "Bearer orbit-renewed-token"

    orbit.requests.clear()
    orbit.store.save_task(_task(progress=70))  # renewed token is reused, no new refresh
    assert [r.url.path for r in orbit.requests] == ["/mirofish/tasks/"]


def test_unrecoverable_401_raises_without_leaking_the_token(orbit):
    orbit.valid_tokens = set()
    orbit.refreshed_to = "unused"
    orbit.http._token = "totally-invalid-token"  # refresh itself will 401
    with pytest.raises(StateStoreError) as error:
        orbit.store.save_task(_task())
    assert error.value.status == 401
    assert "totally-invalid-token" not in str(error.value)


def test_http_errors_never_leak_the_token(orbit):
    orbit.fail_next = 1
    with pytest.raises(StateStoreError) as error:
        orbit.http.list("tasks")
    assert error.value.status == 503
    assert TOKEN not in str(error.value)
    assert TOKEN not in repr(orbit.http)


def test_http_requires_configuration():
    with pytest.raises(ValueError):
        OrbitHttp("https://orbit.example", "mirofish", "")


def test_buffer_coalesces_task_updates_and_delivers_in_order(orbit):
    gate = threading.Event()
    saved = []

    class Slow:
        def save_task(self, task):
            gate.wait(2)
            saved.append((task["task_id"], task["progress"]))

        def record_step(self, *a, **k):
            saved.append(("step", a[2]))

    buffered = BufferedStateStore(Slow(), sleep=lambda _s: None)
    buffered.save_task(_task("a", progress=1))   # worker picks this up and blocks
    buffered.save_task(_task("b", progress=1))
    buffered.save_task(_task("b", progress=50))  # coalesced into the queued "b"
    buffered.record_step("graph_build", "a", "chunked", "completed")
    gate.set()

    assert buffered.flush(5)
    assert saved == [("a", 1), ("b", 50), ("step", "chunked")]


def test_buffer_retries_then_drops_without_raising():
    attempts = []

    class Broken:
        def save_task(self, task):
            attempts.append(1)
            raise StateStoreError("down", status=503)

    buffered = BufferedStateStore(Broken(), sleep=lambda _s: None, retry_delays=(0, 0))
    buffered.save_task(_task())  # must not raise
    assert buffered.flush(5) is False
    assert len(attempts) == 3
    assert buffered.dropped_writes == 1


def test_buffer_reads_fail_soft():
    class Broken:
        def load_task(self, _):
            raise StateStoreError("down")

        def list_tasks(self, **_):
            raise StateStoreError("down")

        def list_steps(self, *_):
            raise StateStoreError("down")

    buffered = BufferedStateStore(Broken(), sleep=lambda _s: None)
    assert buffered.load_task("x") is None
    assert buffered.list_tasks() == []
    assert buffered.list_steps("a", "b") == []


def test_task_manager_mirrors_every_state_change(monkeypatch):
    mirrored = []

    class Recorder(NullStateStore):
        def save_task(self, task):
            mirrored.append((task["status"], task["progress"], task["metadata"]))

    state_store.reset_state_store(Recorder())
    try:
        manager = TaskManager()
        task_id = manager.create_task("graph_build", metadata={"project_id": "p1"})
        manager.update_task(task_id, status=TaskStatus.PROCESSING, progress=20)
        manager.complete_task(task_id, {"ok": True})
        manager.update_task("does-not-exist", progress=1)  # unknown id: no mirror
    finally:
        state_store.reset_state_store(None)

    assert mirrored == [
        ("pending", 0, {"project_id": "p1"}),
        ("processing", 20, {"project_id": "p1"}),
        ("completed", 100, {"project_id": "p1"}),
    ]


def test_task_manager_survives_a_broken_store():
    class Exploding(NullStateStore):
        def save_task(self, task):
            raise RuntimeError("boom")

    state_store.reset_state_store(Exploding())
    try:
        manager = TaskManager()
        task_id = manager.create_task("graph_build")
        manager.update_task(task_id, progress=5)
        assert manager.get_task(task_id).progress == 5
    finally:
        state_store.reset_state_store(None)


def test_reconcile_closes_only_stale_active_tasks(orbit, monkeypatch):
    store = orbit.store
    store.save_task(_task("running", status="processing"))
    store.save_task(_task("pending", status="pending"))
    store.save_task(_task("done", status="completed"))
    state_store.reset_state_store(store)
    monkeypatch.setattr(Config, "ORBIT_ORPHAN_GRACE_SECONDS", 0)
    try:
        assert state_store.reconcile_orphan_tasks() == 2
    finally:
        state_store.reset_state_store(None)

    status = {r["task_id"]: r["status"] for r in orbit.tables["tasks"]}
    assert status == {"running": "failed", "pending": "failed", "done": "completed"}
    assert "Interrupted" in next(
        r["error"] for r in orbit.tables["tasks"] if r["task_id"] == "running"
    )


def test_reconcile_respects_the_grace_period(orbit, monkeypatch):
    from datetime import datetime, timezone

    fresh = datetime.now(timezone.utc).isoformat()
    orbit.store.save_task(_task("fresh", status="processing", updated_at=fresh))
    orbit.store.save_task(_task("old", status="processing"))
    state_store.reset_state_store(orbit.store)
    monkeypatch.setattr(Config, "ORBIT_ORPHAN_GRACE_SECONDS", 300)
    try:
        assert state_store.reconcile_orphan_tasks() == 1
    finally:
        state_store.reset_state_store(None)

    status = {r["task_id"]: r["status"] for r in orbit.tables["tasks"]}
    assert status == {"fresh": "processing", "old": "failed"}


def test_store_is_a_noop_until_orbit_is_configured(monkeypatch):
    monkeypatch.setattr(Config, "ORBIT_BASE_URL", "")
    monkeypatch.setattr(Config, "ORBIT_API_TOKEN", "")
    state_store.reset_state_store(None)
    assert isinstance(state_store.get_state_store(), NullStateStore)
    state_store.record_step("graph_build", "t", "chunked", "completed")  # no error

    monkeypatch.setattr(Config, "ORBIT_BASE_URL", "https://orbit.example")
    monkeypatch.setattr(Config, "ORBIT_API_TOKEN", TOKEN)
    state_store.reset_state_store(None)
    try:
        assert isinstance(state_store.get_state_store(), BufferedStateStore)
    finally:
        state_store.reset_state_store(None)
