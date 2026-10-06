"""Contract tests for the backend-neutral graph layer."""

import pathlib
import re
from types import SimpleNamespace

import pytest
from zep_cloud import NotFoundError

from app.config import Config
from app.services import graph_backend
from app.services.graph_backend import (
    GraphBackend,
    GraphNotFoundError,
    get_graph_backend,
)
from app.services.graph_backend.ontology import normalize_ontology
from app.services.graph_backend.zep_backend import ZepBackend


def _not_found():
    return NotFoundError(body={"message": "missing"})


def test_zep_backend_satisfies_the_contract():
    assert isinstance(ZepBackend(SimpleNamespace()), GraphBackend)


def test_nodes_and_edges_are_translated_to_neutral_models(monkeypatch):
    node = SimpleNamespace(
        uuid_="n1", name="Ana", labels=["Entity", "Person"], summary=None,
        attributes=None, created_at="2026-01-01",
    )
    edge = SimpleNamespace(
        uuid_="e1", name="KNOWS", fact="Ana knows Bia", source_node_uuid="n1",
        target_node_uuid="n2", attributes={"k": "v"}, fact_type=None,
        created_at="c", valid_at="v", invalid_at=None, expired_at=None,
        episodes="ep-1",
    )
    monkeypatch.setattr(
        "app.services.graph_backend.zep_backend.fetch_all_nodes",
        lambda _client, _graph: [node],
    )
    monkeypatch.setattr(
        "app.services.graph_backend.zep_backend.fetch_all_edges",
        lambda _client, _graph: [edge],
    )
    backend = ZepBackend(SimpleNamespace())

    [n] = backend.list_nodes("g")
    assert (n.uuid, n.name, n.labels, n.summary, n.attributes) == (
        "n1", "Ana", ["Entity", "Person"], "", {},
    )

    [e] = backend.list_edges("g")
    assert e.uuid == "e1"
    assert e.fact_type == "KNOWS"  # falls back to the edge name
    assert e.episodes == ["ep-1"]  # scalar is normalised to a list
    assert e.invalid_at is None


def test_not_found_is_translated_and_get_node_returns_none():
    def missing(**_kwargs):
        raise _not_found()

    backend = ZepBackend(SimpleNamespace(
        graph=SimpleNamespace(
            delete=missing,
            node=SimpleNamespace(get=missing),
        ),
    ))

    with pytest.raises(GraphNotFoundError):
        backend.delete_graph("g")
    assert backend.get_node("n1") is None


def test_other_errors_are_not_swallowed_as_not_found():
    def boom(**_kwargs):
        raise PermissionError("denied")

    backend = ZepBackend(SimpleNamespace(
        graph=SimpleNamespace(delete=boom),
    ))
    with pytest.raises(PermissionError):
        backend.delete_graph("g")


def test_search_clamps_inputs_and_returns_neutral_results():
    seen = {}

    def search(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(
            edges=[SimpleNamespace(uuid_="e", fact="f", name="n")],
            nodes=[SimpleNamespace(uuid_="n", name="x", summary="s", labels=["L"])],
        )

    backend = ZepBackend(SimpleNamespace(graph=SimpleNamespace(search=search)))
    result = backend.search("g", "q" * 1000, limit=500, reranker="rrf")

    assert len(seen["query"]) == 400
    assert seen["limit"] == 50
    assert seen["reranker"] == "rrf"
    assert result.edges[0].fact == "f"
    assert result.nodes[0].summary == "s"


def test_add_text_returns_the_episode_uuid_and_rejects_an_empty_one():
    ok = ZepBackend(SimpleNamespace(
        graph=SimpleNamespace(add=lambda **_k: SimpleNamespace(uuid_="ep-1"))
    ))
    assert ok.add_text("g", "text", created_at="t") == "ep-1"

    empty = ZepBackend(SimpleNamespace(
        graph=SimpleNamespace(add=lambda **_k: SimpleNamespace())
    ))
    with pytest.raises(RuntimeError, match="no episode UUID"):
        empty.add_text("g", "text")


def test_ontology_is_normalised_independently_of_any_vendor():
    ontology = normalize_ontology({
        "entity_types": [{
            "name": "Speaker",
            "attributes": ["graph_id", {"name": "role"}],
        }],
        "edge_types": [{
            "name": "works_for",
            "attributes": [],
            "source_targets": [{"source": "Speaker", "target": "Org"}],
        }],
    })

    [speaker] = ontology.entity_types
    assert [a.name for a in speaker.attributes] == ["entity_graph_id", "role"]
    [edge] = ontology.edge_types
    assert edge.class_name == "WorksFor"
    assert edge.source_targets == (("Speaker", "Org"),)


def test_factory_builds_zep_and_rejects_unknown_backends(monkeypatch):
    monkeypatch.setattr(Config, "GRAPH_BACKEND", "zep")
    assert get_graph_backend("test-key").name == "zep"

    monkeypatch.setattr(Config, "GRAPH_BACKEND", "nope")
    with pytest.raises(ValueError, match="Unsupported GRAPH_BACKEND"):
        get_graph_backend("test-key")


def test_config_validation_reports_an_unknown_backend(monkeypatch):
    monkeypatch.setattr(Config, "LLM_API_KEY", "k")
    monkeypatch.setattr(Config, "GRAPH_BACKEND", "nope")
    assert any("GRAPH_BACKEND" in error for error in Config.validate())

    monkeypatch.setattr(Config, "GRAPH_BACKEND", "zep")
    monkeypatch.setattr(Config, "ZEP_API_KEY", None)
    assert any("ZEP_API_KEY" in error for error in Config.validate())


def test_vendor_sdk_does_not_leak_outside_the_backend():
    """Only the Zep backend and its helpers may import ``zep_cloud``."""

    app_root = pathlib.Path(graph_backend.__file__).resolve().parents[2]
    allowed = {
        app_root / "services" / "graph_backend" / "zep_backend.py",
        app_root / "utils" / "zep.py",
        app_root / "utils" / "zep_paging.py",
    }
    pattern = re.compile(r"^\s*(from|import)\s+zep_cloud\b", re.MULTILINE)
    offenders = [
        str(path.relative_to(app_root))
        for path in app_root.rglob("*.py")
        if path not in allowed and pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []
