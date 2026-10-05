import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import llm_env  # noqa: E402

KEYS = [
    "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL_NAME",
    "LLM_BOOST_API_KEY", "LLM_BOOST_BASE_URL", "LLM_BOOST_MODEL_NAME",
    "LLM_SIM_API_KEY", "LLM_SIM_BASE_URL", "LLM_SIM_MODEL_NAME",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LLM_API_KEY", "general-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://cloud.example/v1")
    monkeypatch.setenv("LLM_MODEL_NAME", "cloud-model")


def test_general_config_by_default():
    key, url, model, _ = llm_env.resolve_llm_settings({})
    assert (key, url, model) == ("general-key", "https://cloud.example/v1", "cloud-model")


def test_model_falls_back_to_simulation_config(monkeypatch):
    monkeypatch.delenv("LLM_MODEL_NAME")
    assert llm_env.resolve_llm_settings({"llm_model": "cfg-model"})[2] == "cfg-model"


def test_boost_only_when_requested(monkeypatch):
    monkeypatch.setenv("LLM_BOOST_API_KEY", "boost-key")
    monkeypatch.setenv("LLM_BOOST_BASE_URL", "https://boost.example/v1")
    assert llm_env.resolve_llm_settings({}, prefer_boost=False)[0] == "general-key"
    key, url, model, _ = llm_env.resolve_llm_settings({}, prefer_boost=True)
    assert (key, url, model) == ("boost-key", "https://boost.example/v1", "cloud-model")


def test_sim_overrides_general_and_boost_without_leaking_general_key(monkeypatch):
    monkeypatch.setenv("LLM_BOOST_API_KEY", "boost-key")
    monkeypatch.setenv("LLM_SIM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_SIM_MODEL_NAME", "local-model")
    for boost in (False, True):
        key, url, model, _ = llm_env.resolve_llm_settings({}, prefer_boost=boost)
        assert (url, model) == ("http://localhost:11434/v1", "local-model")
        assert key == "not-needed"  # chave da nuvem não vai para o endpoint local


def test_sim_reuses_general_key_when_same_endpoint(monkeypatch):
    monkeypatch.setenv("LLM_SIM_MODEL_NAME", "cheap-cloud-model")
    key, url, model, _ = llm_env.resolve_llm_settings({})
    assert (key, url, model) == ("general-key", "https://cloud.example/v1", "cheap-cloud-model")


def test_explicit_sim_key_is_used(monkeypatch):
    monkeypatch.setenv("LLM_SIM_MODEL_NAME", "m")
    monkeypatch.setenv("LLM_SIM_BASE_URL", "https://other.example/v1")
    monkeypatch.setenv("LLM_SIM_API_KEY", "sim-key")
    assert llm_env.resolve_llm_settings({})[0] == "sim-key"


def test_reasoning_effort_precedence_and_validation(monkeypatch):
    monkeypatch.delenv("LLM_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("LLM_SIM_REASONING_EFFORT", raising=False)
    assert llm_env.resolve_reasoning_effort() is None
    monkeypatch.setenv("LLM_REASONING_EFFORT", "none")
    assert llm_env.resolve_reasoning_effort() == "none"
    monkeypatch.setenv("LLM_SIM_REASONING_EFFORT", "LOW")
    assert llm_env.resolve_reasoning_effort() == "low"
    monkeypatch.setenv("LLM_SIM_REASONING_EFFORT", "banana")
    assert llm_env.resolve_reasoning_effort() == "none"


def test_chat_completion_sends_reasoning_effort_only_when_configured(monkeypatch):
    from app.utils.openai_chat_compat import create_chat_completion

    captured = {}

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)

    class Chat:
        completions = Completions()

    class Client:
        chat = Chat()

    monkeypatch.delenv("LLM_REASONING_EFFORT", raising=False)
    create_chat_completion(Client(), model="m", messages=[])
    assert "extra_body" not in captured

    monkeypatch.setenv("LLM_REASONING_EFFORT", "none")
    create_chat_completion(Client(), model="m", messages=[])
    assert captured["extra_body"] == {"reasoning_effort": "none"}
