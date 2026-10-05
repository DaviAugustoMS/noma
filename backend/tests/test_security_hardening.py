import pytest

from app import create_app
from app.config import Config


@pytest.fixture()
def client():
    class TestConfig(Config):
        TESTING = True

    return create_app(TestConfig).test_client()


@pytest.mark.parametrize("path", [
    "/api/simulation/..",
    "/api/simulation/.%2e/config",
    "/api/graph/project/..",
    "/api/report/bad.id",
])
def test_unsafe_route_ids_are_rejected(client, path):
    response = client.get(path)
    assert response.status_code in (400, 404)
    assert response.status_code != 200


def test_dot_dot_simulation_id_returns_400(client):
    response = client.get("/api/simulation/../run-status")
    assert response.status_code in (400, 404)
    response = client.get("/api/simulation/%2e%2e/config")
    assert response.status_code in (400, 404)


def test_body_ids_are_validated(client):
    response = client.post("/api/simulation/start", json={"simulation_id": "../etc"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid simulation_id"


def test_valid_id_passes_validation_layer(client):
    response = client.get("/api/simulation/sim_abcdef123456")
    assert response.status_code != 400


def test_error_responses_do_not_expose_traceback(client, monkeypatch):
    from app.api import graph as graph_api

    def boom(*args, **kwargs):
        raise RuntimeError("falha interna")

    monkeypatch.setattr(graph_api.ProjectManager, "get_project", boom, raising=False)
    response = client.get("/api/graph/project/proj_abc123")
    assert response.status_code == 500
    assert "traceback" not in response.get_json()
