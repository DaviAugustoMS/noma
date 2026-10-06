"""Proteção das rotas /api/*: token validado no Orbit + lista de emails permitidos."""

import logging

import httpx
import pytest

from app import create_app
from app.config import Config
from app.utils import api_auth

ALLOWED = "ana@exemplo.com"
STRANGER = "intruso@exemplo.com"
GOOD = "tok-good-123456"
OTHER = "tok-other-654321"
ROUTE = "/api/graph/tasks"   # GET leve, sem chamadas externas


class FakeOrbit:
    def __init__(self):
        self.calls = []
        self.mode = "ok"      # ok | down | error500 | badjson | noemail
        self.users = {GOOD: ALLOWED, OTHER: STRANGER}

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/mirofish/auth/me"
        token = request.headers["Authorization"].removeprefix("Bearer ")
        self.calls.append(token)
        if self.mode == "down":
            raise httpx.ConnectError("orbit fora do ar")
        if self.mode == "error500":
            return httpx.Response(500)
        if self.mode == "badjson":
            return httpx.Response(200, content=b"<html>nao e json</html>")
        email = self.users.get(token)
        if email is None:
            return httpx.Response(401, json={"error": "unauthorized"})
        return httpx.Response(200, json={"id": "u1", "email": ("" if self.mode == "noemail" else email)})


@pytest.fixture
def orbit(monkeypatch):
    fake = FakeOrbit()
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", True)
    monkeypatch.setattr(Config, "API_ALLOWED_EMAILS", (ALLOWED,))
    monkeypatch.setattr(Config, "ORBIT_BASE_URL", "https://orbit.example")
    monkeypatch.setattr(Config, "ORBIT_APP", "mirofish")
    api_auth.reset_for_tests(httpx.Client(transport=httpx.MockTransport(fake.handler)))
    fake.client = create_app().test_client()
    return fake


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_missing_or_malformed_token_is_401_and_never_asks_orbit(orbit):
    for headers in ({}, {"Authorization": ""}, {"Authorization": "Bearer "}, {"Authorization": "Basic abc"}, {"Authorization": GOOD}):
        r = orbit.client.get(ROUTE, headers=headers)
        assert r.status_code == 401, headers
        assert r.get_json()["code"] == "auth_required"
        assert r.headers["WWW-Authenticate"] == "Bearer"
    assert orbit.calls == []


def test_invalid_token_is_401(orbit):
    r = orbit.client.get(ROUTE, headers=bearer("tok-desconhecido"))
    assert r.status_code == 401 and r.get_json()["code"] == "auth_invalid"
    assert r.get_json()["success"] is False


def test_valid_token_but_email_outside_the_allowlist_is_403(orbit):
    r = orbit.client.get(ROUTE, headers=bearer(OTHER))
    assert r.status_code == 403 and r.get_json()["code"] == "auth_forbidden"


def test_allowed_user_passes_and_allowlist_ignores_case(orbit, monkeypatch):
    assert orbit.client.get(ROUTE, headers=bearer(GOOD)).status_code == 200
    api_auth.reset_for_tests(httpx.Client(transport=httpx.MockTransport(orbit.handler)))
    monkeypatch.setattr(Config, "API_ALLOWED_EMAILS", (ALLOWED.upper(),))
    assert orbit.client.get(ROUTE, headers=bearer(GOOD)).status_code == 200


def test_orbit_is_asked_once_per_token_within_the_ttl(orbit):
    for _ in range(5):
        assert orbit.client.get(ROUTE, headers=bearer(GOOD)).status_code == 200
    assert orbit.calls == [GOOD]


def test_invalid_tokens_are_negatively_cached_too(orbit):
    for _ in range(4):
        assert orbit.client.get(ROUTE, headers=bearer("lixo")).status_code == 401
    assert orbit.calls == ["lixo"]


@pytest.mark.parametrize("mode", ["down", "error500", "badjson", "noemail"])
def test_orbit_failures_fail_closed_with_503(orbit, mode):
    orbit.mode = mode
    r = orbit.client.get(ROUTE, headers=bearer(GOOD))
    assert r.status_code == 503 and r.get_json()["code"] == "auth_unavailable"


def test_a_503_is_not_cached_so_recovery_is_immediate(orbit):
    orbit.mode = "down"
    assert orbit.client.get(ROUTE, headers=bearer(GOOD)).status_code == 503
    orbit.mode = "ok"
    assert orbit.client.get(ROUTE, headers=bearer(GOOD)).status_code == 200


def test_preflight_and_health_stay_open(orbit):
    pre = orbit.client.options(ROUTE, headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"})
    assert pre.status_code in (200, 204)
    assert orbit.client.get("/health").status_code == 200
    assert orbit.calls == []


def test_protection_can_be_turned_off(orbit, monkeypatch):
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", False)
    assert create_app().test_client().get(ROUTE).status_code == 200


def test_cache_is_bounded(orbit, monkeypatch):
    monkeypatch.setattr(Config, "API_AUTH_CACHE_MAX", 3)
    for n in range(10):
        orbit.users[f"t{n}"] = ALLOWED
        assert orbit.client.get(ROUTE, headers=bearer(f"t{n}")).status_code == 200
    assert len(api_auth._cache._items) <= 3


def test_token_never_reaches_logs_or_the_cache_in_clear(orbit, caplog):
    caplog.set_level(logging.DEBUG)
    orbit.client.get(ROUTE, headers=bearer(GOOD))
    orbit.client.get(ROUTE, headers=bearer("tok-desconhecido"))
    assert GOOD not in caplog.text and "tok-desconhecido" not in caplog.text
    assert GOOD not in api_auth._cache._items and all(len(k) == 64 for k in api_auth._cache._items)


def test_messages_follow_the_requested_language(orbit):
    r = orbit.client.get(ROUTE, headers={"Accept-Language": "en"})
    assert r.status_code == 401 and "Sign in" in r.get_json()["error"]
    r = orbit.client.get(ROUTE)
    assert "login" in r.get_json()["error"].lower()           # padrão: português


def test_config_refuses_to_start_unprotected(monkeypatch):
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", True)
    monkeypatch.setattr(Config, "ORBIT_BASE_URL", "")
    monkeypatch.setattr(Config, "API_ALLOWED_EMAILS", ())
    errors = Config.validate()
    assert any("ORBIT_BASE_URL" in e for e in errors)
    assert any("API_ALLOWED_EMAILS" in e for e in errors)

    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", False)
    assert not any("API_ALLOWED_EMAILS" in e for e in Config.validate())
