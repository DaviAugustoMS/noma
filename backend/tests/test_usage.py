import json
import threading
from types import SimpleNamespace

import pytest

from app import create_app
from app.config import Config
from app.utils import usage
from app.utils.openai_chat_compat import create_chat_completion


def _response(prompt=10, completion=5, content="ok"):
    return SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion),
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
    )


class _Client:
    def __init__(self, response):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: response))


def test_completion_is_counted_in_the_bound_project_and_stage():
    usage.bind("proj_a", "ontology")
    create_chat_completion(_Client(_response(100, 40)), model="m", messages=[{"role": "user", "content": "oi"}])
    data = usage.project_usage("proj_a")
    assert data["total_tokens"] == 140 and data["calls"] == 1
    assert data["stages"]["ontology"]["prompt_tokens"] == 100


def test_missing_usage_is_estimated_and_flagged():
    usage.bind("proj_a", "report")
    response = SimpleNamespace(usage=None, choices=[SimpleNamespace(message=SimpleNamespace(content="x" * 40))])
    create_chat_completion(_Client(response), model="m", messages=[{"role": "user", "content": "y" * 80}])
    data = usage.project_usage("proj_a")
    assert data["estimated_calls"] == 1 and data["prompt_tokens"] == 20 and data["completion_tokens"] == 10


def test_unscoped_calls_still_count_in_the_grand_total():
    usage.bind(None, "other")
    usage.add(*usage.current_scope(), 7, 3)
    usage.bind("proj_a", "chat")
    usage.add(*usage.current_scope(), 1, 1)
    assert usage.all_usage()["total_tokens"] == 12


def test_threads_inherit_the_scope_only_through_in_context():
    usage.bind("proj_t", "prepare")
    seen = {}

    def work(key):
        seen[key] = usage.current_scope()

    plain = threading.Thread(target=work, args=("plain",))
    wrapped = threading.Thread(target=usage.in_context(work), args=("wrapped",))
    for t in (plain, wrapped):
        t.start()
        t.join()
    assert seen["wrapped"] == ("proj_t", "prepare")
    assert seen["plain"] == (usage.SEM_PROJETO, "other")


def test_concurrent_writes_do_not_lose_tokens():
    def burst():
        for _ in range(25):
            usage.add("proj_c", "chat", 2, 1)

    threads = [threading.Thread(target=burst) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert usage.project_usage("proj_c")["total_tokens"] == 8 * 25 * 3


def test_invalid_ids_and_negative_values_are_contained():
    usage.bind("../../etc/passwd", "chat")
    assert usage.current_scope()[0] == usage.SEM_PROJETO
    usage.add("proj_n", "chat", -50, 10)
    assert usage.project_usage("proj_n")["total_tokens"] == 10


def test_capture_returns_only_what_happened_inside():
    usage.add("proj_x", "chat", 5, 5)
    with usage.capture() as spent:
        usage.add("proj_x", "chat", 3, 2)
    assert spent.as_dict()["total_tokens"] == 5 and spent.calls == 1


def test_cost_only_when_prices_are_configured(monkeypatch):
    usage.add("proj_p", "chat", 1_000_000, 500_000)
    assert usage.project_usage("proj_p")["cost"] is None
    monkeypatch.setattr(Config, "LLM_PRICE_INPUT_PER_1M", 2.0)
    monkeypatch.setattr(Config, "LLM_PRICE_OUTPUT_PER_1M", 4.0)
    monkeypatch.setattr(Config, "LLM_PRICE_CURRENCY", "BRL")
    data = usage.project_usage("proj_p")
    assert data["cost"] == 4.0 and data["currency"] == "BRL"


def test_move_seed_transfers_without_double_counting_and_is_clamped():
    usage.bind(None, "seed")
    usage.add(*usage.current_scope(), 100, 50)
    usage.move_seed("proj_m", 100, 50, 1)
    assert usage.project_usage("proj_m")["stages"]["seed"]["total_tokens"] == 150
    assert usage.all_usage()["total_tokens"] == 150  # não dobrou
    usage.move_seed("proj_m", 10**9, 10**9, 10**9)  # número forjado pelo cliente
    assert usage.all_usage()["total_tokens"] == 150


def test_simulation_subprocess_file_is_added_to_the_project(monkeypatch, tmp_path):
    sim_dir = tmp_path / "sim_1"
    sim_dir.mkdir()
    (sim_dir / "llm_usage.json").write_text(json.dumps({"prompt_tokens": 70, "completion_tokens": 30, "calls": 4}))
    from app.services import simulation_manager

    monkeypatch.setattr(simulation_manager.SimulationManager, "SIMULATION_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        simulation_manager.SimulationManager, "list_simulations",
        lambda self, project_id=None: [SimpleNamespace(simulation_id="sim_1")],
    )
    data = usage.project_usage("proj_s")
    assert data["stages"]["simulation"]["total_tokens"] == 100 and data["total_tokens"] == 100


def test_usage_route_returns_total_and_project():
    usage.add("proj_r", "chat", 4, 6)
    client = create_app().test_client()
    assert client.get("/api/usage").get_json()["data"]["total_tokens"] == 10
    body = client.get("/api/usage?project_id=proj_zzz").get_json()["data"]
    assert body["total_tokens"] == 0  # projeto inexistente não vaza o total de outros
