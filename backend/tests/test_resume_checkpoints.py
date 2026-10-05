import json
from types import SimpleNamespace

import pytest

from app import create_app
from app.api import graph as graph_api
from app.api import simulation as simulation_api
from app.config import Config
from app.models.project import ProjectStatus
from app.models.task import TaskManager, TaskStatus
from app.services import oasis_profile_generator as opg
from app.services.oasis_profile_generator import OasisAgentProfile, OasisProfileGenerator


def _entity(name, uuid):
    return SimpleNamespace(
        name=name, uuid=uuid, summary=f"resumo de {name}", get_entity_type=lambda: "Person"
    )


def _generator(fail_names=()):
    gen = OasisProfileGenerator.__new__(OasisProfileGenerator)
    gen.graph_id = None
    calls = []

    def fake_generate(entity, user_id, use_llm):
        calls.append(entity.name)
        if entity.name in fail_names:
            raise RuntimeError("LLM caiu")
        return OasisAgentProfile(
            user_id=user_id, user_name=entity.name.lower(), name=entity.name,
            bio=f"bio {entity.name}", persona="persona", source_entity_uuid=entity.uuid,
        )

    gen.generate_profile_from_entity = fake_generate
    gen._print_generated_profile = lambda *a, **k: None
    return gen, calls


def test_profiles_resume_from_checkpoint_and_retry_only_failures(tmp_path):
    ckpt = str(tmp_path / "profiles_checkpoint.json")
    entities = [_entity("Ana", "u1"), _entity("Bia", "u2"), _entity("Caio", "u3")]

    gen, calls = _generator(fail_names={"Bia"})
    first = gen.generate_profiles_from_entities(entities, use_llm=True, parallel_count=1, checkpoint_path=ckpt)
    assert sorted(calls) == ["Ana", "Bia", "Caio"]
    assert [p.name for p in first] == ["Ana", "Bia", "Caio"]  # Bia usa perfil de reserva

    saved = json.load(open(ckpt, encoding="utf-8"))["profiles"]
    assert set(saved) == {"u1", "u3"}  # reserva não é gravada no checkpoint

    gen2, calls2 = _generator()
    second = gen2.generate_profiles_from_entities(entities, use_llm=True, parallel_count=1, checkpoint_path=ckpt)
    assert calls2 == ["Bia"]  # só o que falhou é gerado de novo
    assert [p.user_id for p in second] == [0, 1, 2]
    assert second[1].bio == "bio Bia"


def test_checkpoint_ignored_when_use_llm_changes_or_file_is_corrupt(tmp_path):
    ckpt = tmp_path / "profiles_checkpoint.json"
    opg.write_profile_checkpoint(str(ckpt), True, {"u1": {"user_id": 0}})
    assert opg.load_profile_checkpoint(str(ckpt), False) == {}
    assert opg.load_profile_checkpoint(str(ckpt), True) == {"u1": {"user_id": 0}}

    ckpt.write_text("{ não é json", encoding="utf-8")
    assert opg.load_profile_checkpoint(str(ckpt), True) == {}
    assert opg.load_profile_checkpoint(str(tmp_path / "nao_existe.json"), True) == {}


def test_find_active_prepare_task_returns_only_running_task_for_that_simulation():
    manager = TaskManager()
    done = manager.create_task("simulation_prepare", {"simulation_id": "sim_a"})
    manager.complete_task(done, {})
    running = manager.create_task("simulation_prepare", {"simulation_id": "sim_a"})
    manager.update_task(running, status=TaskStatus.PROCESSING, progress=30)
    other = manager.create_task("simulation_prepare", {"simulation_id": "sim_b"})

    found = simulation_api._find_active_prepare_task("sim_a")
    assert found["task_id"] == running
    assert simulation_api._find_active_prepare_task("sim_b")["task_id"] == other
    assert simulation_api._find_active_prepare_task("sim_inexistente") is None


@pytest.fixture()
def client():
    class TestConfig(Config):
        TESTING = True

    return create_app(TestConfig).test_client()


def _project(status, ontology=None):
    saved = {}
    project = SimpleNamespace(
        project_id="proj_abc", name="p", status=status, ontology=ontology, error="falha",
        simulation_requirement="prever", analysis_summary="", files=[], total_text_length=10,
    )
    return project, saved


def test_ontology_retry_reuses_stored_text(client, monkeypatch):
    project, _ = _project(ProjectStatus.FAILED)
    persisted = []
    monkeypatch.setattr(graph_api.ProjectManager, "get_project", lambda pid: project)
    monkeypatch.setattr(graph_api.ProjectManager, "get_extracted_text", lambda pid: "texto salvo")
    monkeypatch.setattr(graph_api.ProjectManager, "save_project", lambda p: persisted.append(p.status))

    captured = {}

    class FakeGenerator:
        def generate(self, document_texts, simulation_requirement, additional_context=None):
            captured["texts"] = document_texts
            return {"entity_types": [{"name": "A"}], "edge_types": [], "analysis_summary": "ok"}

    monkeypatch.setattr(graph_api, "OntologyGenerator", FakeGenerator)

    response = client.post("/api/graph/ontology/retry", json={"project_id": "proj_abc"})
    assert response.status_code == 200
    assert captured["texts"] == ["texto salvo"]
    assert project.status == ProjectStatus.ONTOLOGY_GENERATED and project.error is None
    assert persisted == [ProjectStatus.ONTOLOGY_GENERATED]


def test_ontology_retry_rejects_wrong_state_and_missing_text(client, monkeypatch):
    done, _ = _project(ProjectStatus.ONTOLOGY_GENERATED, ontology={"entity_types": []})
    monkeypatch.setattr(graph_api.ProjectManager, "get_project", lambda pid: done)
    assert client.post("/api/graph/ontology/retry", json={"project_id": "proj_abc"}).status_code == 409

    failed, _ = _project(ProjectStatus.FAILED)
    monkeypatch.setattr(graph_api.ProjectManager, "get_project", lambda pid: failed)
    monkeypatch.setattr(graph_api.ProjectManager, "get_extracted_text", lambda pid: "")
    assert client.post("/api/graph/ontology/retry", json={"project_id": "proj_abc"}).status_code == 422

    assert client.post("/api/graph/ontology/retry", json={}).status_code == 400


def test_ontology_retry_failure_keeps_project_id_for_the_client(client, monkeypatch):
    project, _ = _project(ProjectStatus.FAILED)
    monkeypatch.setattr(graph_api.ProjectManager, "get_project", lambda pid: project)
    monkeypatch.setattr(graph_api.ProjectManager, "get_extracted_text", lambda pid: "texto")
    monkeypatch.setattr(graph_api.ProjectManager, "save_project", lambda p: None)

    class Boom:
        def generate(self, **kwargs):
            raise RuntimeError("sem LLM")

    monkeypatch.setattr(graph_api, "OntologyGenerator", Boom)
    response = client.post("/api/graph/ontology/retry", json={"project_id": "proj_abc"})
    assert response.status_code == 500
    assert response.get_json()["data"] == {"project_id": "proj_abc"}
    assert project.status == ProjectStatus.FAILED
