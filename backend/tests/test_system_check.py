import httpx
import pytest

from app import create_app
from app.api import system as system_api
from app.config import Config


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(Config, "LLM_API_KEY", "secret-llm-key", raising=False)
    monkeypatch.setattr(Config, "LLM_BASE_URL", "http://127.0.0.1:11435/v1", raising=False)
    monkeypatch.setattr(Config, "LLM_MODEL_NAME", "modelo-x", raising=False)
    monkeypatch.setattr(Config, "ZEP_API_KEY", "secret-zep-key", raising=False)
    system_api._cache.update({"at": 0.0, "value": None})

    class TestConfig(Config):
        TESTING = True

    return create_app(TestConfig).test_client()


def _fake_get(llm_error=None, llm_status=200, zep_error=None):
    def fake(url, **kwargs):
        if "/models" in url:
            if llm_error:
                raise llm_error
            return httpx.Response(llm_status, request=httpx.Request("GET", url))
        if zep_error:
            raise zep_error
        return httpx.Response(200, request=httpx.Request("GET", url))

    return fake


def test_all_dependencies_up(client, monkeypatch):
    monkeypatch.setattr(system_api.httpx, "get", _fake_get())
    data = client.get("/api/system/check").get_json()["data"]
    assert data["ok"] is True
    assert data["llm"]["endpoint"] == "127.0.0.1:11435"
    assert data["llm"]["model"] == "modelo-x"


def test_llm_down_reports_connection_refused_without_leaking_secrets(client, monkeypatch):
    monkeypatch.setattr(system_api.httpx, "get", _fake_get(llm_error=httpx.ConnectError("boom")))
    response = client.get("/api/system/check")
    data = response.get_json()["data"]
    assert data["ok"] is False
    assert data["llm"]["reachable"] is False
    assert data["llm"]["reason"] == "connection_refused"
    assert data["zep"]["reachable"] is True
    body = response.get_data(as_text=True)
    assert "secret-llm-key" not in body and "secret-zep-key" not in body


def test_unauthorized_and_missing_config(client, monkeypatch):
    monkeypatch.setattr(system_api.httpx, "get", _fake_get(llm_status=401))
    assert client.get("/api/system/check").get_json()["data"]["llm"]["reason"] == "unauthorized"

    system_api._cache.update({"at": 0.0, "value": None})
    monkeypatch.setattr(Config, "ZEP_API_KEY", None, raising=False)
    zep = client.get("/api/system/check").get_json()["data"]["zep"]
    assert zep["configured"] is False and zep["reason"] == "not_configured"


def test_results_are_cached(client, monkeypatch):
    calls = []

    def counting(url, **kwargs):
        calls.append(url)
        return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr(system_api.httpx, "get", counting)
    client.get("/api/system/check")
    client.get("/api/system/check")
    assert len(calls) == 2  # 1 LLM + 1 Zep, segunda chamada veio do cache
