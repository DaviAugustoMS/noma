"""Todas as chamadas ao LLM: prompt em inglês + regra de idioma (no sistema e no fim da mensagem do usuário)."""

import json
import re
from types import SimpleNamespace

import pytest

from app.config import Config
from app.services import simulation_config_generator as config_module
from app.services import zep_tools
from app.services.ontology_generator import OntologyGenerator
from app.utils import locale as locale_utils

CJK = re.compile(r"[一-鿿]")
LANGS = [("pt", "Brazilian Portuguese"), ("en", "English"), ("zh", "Simplified Chinese")]


class RecordingLLM:
    """LLM falso: guarda as mensagens e devolve respostas mínimas válidas."""

    def __init__(self):
        self.calls = []

    def chat_json(self, messages, **kwargs):
        self.calls.append(messages)
        return {
            "sub_queries": ["a", "b"],
            "questions": ["q1?", "q2?"],
            "entity_types": [],
            "edge_types": [],
            "analysis_summary": "ok",
        }

    def chat(self, messages, **kwargs):
        self.calls.append(messages)
        return "resumo"


def _roles(messages):
    return {m["role"]: m["content"] for m in messages}


def _assert_rule_and_english_prompt(messages, json_rule, name):
    sysmsg, usermsg = _roles(messages)["system"], _roles(messages)["user"]
    rule = (
        locale_utils.get_json_language_instruction()
        if json_rule
        else locale_utils.get_language_instruction()
    )
    assert rule in sysmsg, "a regra de idioma precisa estar no prompt de sistema"
    assert usermsg.rstrip().endswith(rule), "e repetida no fim da mensagem do usuário (modelos locais)"
    if json_rule:
        assert name in rule
    # o texto do prompt em si é inglês: chinês só pode vir da regra do zh e dos dados do usuário
    assert not CJK.search(sysmsg.replace(rule, ""))


@pytest.mark.parametrize("code,name", LANGS)
def test_zep_tools_json_calls_carry_the_json_language_rule(code, name):
    locale_utils.set_locale(code)
    llm = RecordingLLM()
    svc = object.__new__(zep_tools.ZepToolsService)
    svc._llm_client = llm

    assert svc._generate_sub_queries("Como reagiram?", "Simular reação", "", 3) == ["a", "b"]
    assert svc._generate_interview_questions("Opinião", "Simular", [{"profession": "Estudante"}]) == ["q1?", "q2?"]

    assert len(llm.calls) == 2
    for messages in llm.calls:
        _assert_rule_and_english_prompt(messages, json_rule=True, name=name)


@pytest.mark.parametrize("code,name", LANGS)
def test_zep_tools_summary_carries_the_free_text_language_rule(code, name):
    locale_utils.set_locale(code)
    llm = RecordingLLM()
    svc = object.__new__(zep_tools.ZepToolsService)
    svc._llm_client = llm
    interview = zep_tools.AgentInterview(
        agent_name="Ana", agent_role="Estudante", agent_bio="bio",
        question="Pergunta?", response="Resposta longa o bastante para o resumo.",
    )

    assert svc._generate_interview_summary([interview], "Opinião") == "resumo"
    _assert_rule_and_english_prompt(llm.calls[0], json_rule=False, name=name)


@pytest.mark.parametrize("code,name", LANGS)
def test_ontology_prompt_is_english_with_the_json_rule_in_both_messages(code, name):
    locale_utils.set_locale(code)
    llm = RecordingLLM()
    OntologyGenerator(llm_client=llm).generate(["Texto de exemplo."], "Simular a discussão.")

    messages = llm.calls[0]
    _assert_rule_and_english_prompt(messages, json_rule=True, name=name)
    # nomes de tipos continuam em inglês, qualquer que seja o idioma escolhido
    assert "PascalCase" in _roles(messages)["system"]


@pytest.mark.parametrize("code,name", LANGS)
def test_time_config_prompt_is_english_with_the_json_rule(monkeypatch, code, name):
    locale_utils.set_locale(code)
    monkeypatch.setattr(Config, "LLM_API_KEY", "test-key")
    captured = []

    def fake_completion(client, **kwargs):
        captured.append(kwargs["messages"])
        content = json.dumps({"total_simulation_hours": 24, "minutes_per_round": 60})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="stop")]
        )

    monkeypatch.setattr(config_module, "create_chat_completion", fake_completion)
    monkeypatch.setattr(config_module, "extract_chat_completion_text", lambda r: r.choices[0].message.content)
    generator = config_module.SimulationConfigGenerator()

    generator._call_llm_with_retry("Task: generate the time configuration.", f"System. {locale_utils.get_json_language_instruction()}")

    messages = captured[0]
    rule = locale_utils.get_json_language_instruction()
    assert messages[-1]["content"].rstrip().endswith(rule)


def test_the_interview_prefix_in_zep_tools_is_english_and_asks_for_the_selected_language():
    import inspect

    source = inspect.getsource(zep_tools.ZepToolsService.interview_agents)
    prefix = source[source.index("INTERVIEW_PROMPT_PREFIX = ("):source.index("optimized_prompt =")]
    assert "get_language_instruction()" in prefix
    assert not CJK.search(prefix.replace('"Question X:"', ""))
