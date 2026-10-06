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

EMAIL = "servico@exemplo.com"
PASSWORD = "senha-de-servico-secreta"
LEGACY_TOKEN = "legacy-app-token"


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
        self.valid_tokens = {LEGACY_TOKEN}
        self.valid_refresh = set()
        self.logins = 0
        self.refreshes = 0
        self._counter = 0
        self.requests = []
        self.fail_next = 0

    def _issue(self):
        self._counter += 1
        pair = (f"access-{self._counter}", f"refresh-{self._counter}")
        self.valid_tokens.add(pair[0])
        self.valid_refresh.add(pair[1])
        return {"token": pair[0], "refresh_token": pair[1]}

    def expire_access_tokens(self):
        self.valid_tokens = {LEGACY_TOKEN} if LEGACY_TOKEN in self.valid_tokens else set()

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        parts = request.url.path.strip("/").split("/")
        assert parts[0] == "mirofish"
        if parts[1] == "auth":
            body = json.loads(request.content or b"{}")
            if parts[2] == "login":
                self.logins += 1
                if body.get("email") == EMAIL and body.get("password") == PASSWORD:
                    return httpx.Response(200, json=self._issue())
                return httpx.Response(401, json={"error": "invalid credentials"})
            if parts[2] == "refresh":
                self.refreshes += 1
                if body.get("refresh_token") in self.valid_refresh:
                    self.valid_refresh.discard(body["refresh_token"])
                    return httpx.Response(200, json=self._issue())
                return httpx.Response(401, json={"error": "invalid refresh token"})
            raise AssertionError(parts)
        auth = request.headers["Authorization"].removeprefix("Bearer ")
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

    def data_requests(self):
        return [r for r in self.requests if "/auth/" not in r.url.path]

    @staticmethod
    def _match(value, expr):
        op, _, arg = expr.partition(".")
        if op == "eq":
            return value == arg
        if op == "in":
            return value in arg.split(",")
        raise AssertionError(f"operator {op}")


def _http(fake, **kwargs):
    kwargs.setdefault("email", EMAIL)
    kwargs.setdefault("password", PASSWORD)
    return OrbitHttp(
        "https://orbit.example", "mirofish",
        client=httpx.Client(transport=httpx.MockTransport(fake.handler)), **kwargs,
    )


@pytest.fixture
def orbit():
    fake = FakeOrbit()
    fake.http = _http(fake)
    fake.store = OrbitStateStore(fake.http)
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
    [request] = orbit.data_requests()
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
    assert dict(orbit.data_requests()[0].url.params)["status"] == "in.pending,processing"


def test_first_request_signs_in_once_and_reuses_the_session(orbit):
    orbit.store.save_task(_task())
    orbit.store.save_task(_task(progress=70))
    assert orbit.logins == 1
    paths = [r.url.path for r in orbit.requests]
    assert paths == ["/mirofish/auth/login", "/mirofish/tasks/", "/mirofish/tasks/"]
    login_body = json.loads(orbit.requests[0].content)
    assert login_body == {"email": EMAIL, "password": PASSWORD}
    assert orbit.requests[1].headers["Authorization"] == "Bearer access-1"


def test_expired_access_token_is_renewed_with_the_refresh_token(orbit):
    orbit.store.save_task(_task())            # login -> access-1 / refresh-1
    orbit.expire_access_tokens()              # the access token expires
    orbit.store.save_task(_task(progress=90))

    assert orbit.logins == 1                  # no new login: refresh was enough
    assert orbit.refreshes == 1
    assert orbit.requests[-1].headers["Authorization"] == "Bearer access-2"
    assert orbit.tables["tasks"][0]["progress"] == 90


def test_dead_refresh_token_falls_back_to_a_new_login(orbit):
    orbit.store.save_task(_task())
    orbit.expire_access_tokens()
    orbit.valid_refresh.clear()               # refresh token is no longer valid
    orbit.store.save_task(_task(progress=55))

    assert orbit.refreshes == 1 and orbit.logins == 2
    assert orbit.tables["tasks"][0]["progress"] == 55


def test_wrong_password_fails_fast_and_backs_off():
    fake = FakeOrbit()
    now = {"t": 1000.0}
    http = _http(fake, password="senha-errada", clock=lambda: now["t"])
    store = OrbitStateStore(http)

    with pytest.raises(StateStoreError) as error:
        store.save_task(_task())
    assert error.value.status == 401
    assert "senha-errada" not in str(error.value)
    assert fake.logins == 1

    for _ in range(3):                        # within the backoff: no new login
        with pytest.raises(StateStoreError):
            store.save_task(_task())
    assert fake.logins == 1

    now["t"] += 61                            # after the backoff it tries again
    with pytest.raises(StateStoreError):
        store.save_task(_task())
    assert fake.logins == 2


def test_credentials_and_tokens_never_leak(orbit):
    orbit.store.save_task(_task())
    orbit.fail_next = 1
    with pytest.raises(StateStoreError) as error:
        orbit.http.list("tasks")
    assert error.value.status == 503
    for secret in (PASSWORD, "access-1", "refresh-1"):
        assert secret not in str(error.value)
        assert secret not in repr(orbit.http)


def test_static_token_mode_works_but_cannot_be_renewed():
    fake = FakeOrbit()
    store = OrbitStateStore(
        _http(fake, email="", password="", token=LEGACY_TOKEN)
    )
    store.save_task(_task())
    assert fake.logins == 0 and len(fake.tables["tasks"]) == 1

    fake.valid_tokens.clear()                 # token expired: nothing to renew it with
    with pytest.raises(StateStoreError) as error:
        store.save_task(_task())
    assert error.value.status == 401
    assert fake.logins == 0 and fake.refreshes == 0


def test_http_requires_configuration():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError):
        OrbitHttp("https://orbit.example", "mirofish", client=client)  # no credentials
    with pytest.raises(ValueError):
        OrbitHttp("https://orbit.example", "mirofish", email=EMAIL, client=client)
    with pytest.raises(ValueError):
        OrbitHttp("", "mirofish", email=EMAIL, password=PASSWORD, client=client)


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
    for name, value in (("ORBIT_BASE_URL", ""), ("ORBIT_API_TOKEN", ""),
                        ("ORBIT_SERVICE_EMAIL", ""), ("ORBIT_SERVICE_PASSWORD", "")):
        monkeypatch.setattr(Config, name, value)
    state_store.reset_state_store(None)
    assert isinstance(state_store.get_state_store(), NullStateStore)
    state_store.record_step("graph_build", "t", "chunked", "completed")  # no error

    monkeypatch.setattr(Config, "ORBIT_BASE_URL", "https://orbit.example")
    state_store.reset_state_store(None)
    assert isinstance(state_store.get_state_store(), NullStateStore)  # URL alone is not enough

    monkeypatch.setattr(Config, "ORBIT_SERVICE_EMAIL", EMAIL)
    state_store.reset_state_store(None)
    assert isinstance(state_store.get_state_store(), NullStateStore)  # email without password

    monkeypatch.setattr(Config, "ORBIT_SERVICE_PASSWORD", PASSWORD)
    state_store.reset_state_store(None)
    try:
        assert isinstance(state_store.get_state_store(), BufferedStateStore)
    finally:
        state_store.reset_state_store(None)

    monkeypatch.setattr(Config, "ORBIT_SERVICE_EMAIL", "")
    monkeypatch.setattr(Config, "ORBIT_SERVICE_PASSWORD", "")
    monkeypatch.setattr(Config, "ORBIT_API_TOKEN", LEGACY_TOKEN)  # legacy fallback
    assert state_store.is_state_store_configured()
