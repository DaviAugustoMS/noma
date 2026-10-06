"""Entrevistas: parsers e prompts funcionam nos idiomas do app, não só em chinês."""

import pytest

from app.api import simulation as simulation_api
from app.services import zep_tools
from app.utils import locale as locale_utils


@pytest.mark.parametrize("text,expected", [
    ("Question 1: Acho a medida abusiva", "Acho a medida abusiva"),
    ("Pergunta 2: Concordo parcialmente", "Concordo parcialmente"),
    ("问题3：我不同意这个做法", "我不同意这个做法"),
    ("question 4. depende do contexto", "depende do contexto"),
    ("Sem numeração aqui", "Sem numeração aqui"),
])
def test_question_numbering_is_stripped_in_every_language(text, expected):
    assert zep_tools._QUESTION_PREFIX_RE.sub("", text).strip() == expected


def test_numbered_question_noise_is_detected_in_every_language():
    for noisy in ("Question 2", "pergunta 3", "问题1", "Frage 4"):
        assert zep_tools._QUESTION_NUMBERED_RE.search(noisy)
    assert not zep_tools._QUESTION_NUMBERED_RE.search("uma pergunta qualquer")


def test_key_quotes_work_for_portuguese_answers():
    answer = (
        "Pergunta 1: Acho o reajuste de 18% abusivo e mal comunicado aos estudantes. "
        "Muitos colegas podem abandonar o curso por causa disso. Curto demais."
    )
    quotes = zep_tools._extract_key_quotes(answer)
    assert quotes, "respostas em português precisam gerar citações-chave"
    assert all(q.endswith(".") for q in quotes)
    assert not any(zep_tools._QUESTION_PREFIX_RE.match(q) for q in quotes)
    assert any("abusivo" in q for q in quotes)


def test_key_quotes_work_for_english_and_chinese_answers():
    en = "I think the new tuition policy is unfair to students and badly explained. It hurts access."
    assert any("unfair" in q for q in zep_tools._extract_key_quotes(en))
    zh = "我认为这次学费上涨的做法对学生很不公平，而且沟通方式存在明显问题。希望校方重新考虑。"
    quotes = zep_tools._extract_key_quotes(zh)
    assert quotes and all(q.endswith("。") for q in quotes)


def test_key_quotes_fall_back_to_quoted_text_and_ignore_tool_json():
    # frase longa demais (>150) para a estratégia principal: entra a das aspas
    long_sentence = (
        "Ele afirmou, sem hesitar e repetindo isso diversas vezes durante toda a conversa com os colegas "
        'e professores presentes, que "a medida é injusta com os alunos" e que ninguém foi ouvido antes da decisão final'
    )
    assert len(long_sentence) > 150
    assert zep_tools._extract_key_quotes(long_sentence) == ["a medida é injusta com os alunos"]
    assert zep_tools._extract_key_quotes('{"tool_name": "x", "parameters": {}}') == []


@pytest.mark.parametrize("code,marker", [("pt", "português"), ("en", "English"), ("zh", "中文")])
def test_single_agent_interview_prefix_is_english_and_asks_for_the_selected_language(code, marker):
    locale_utils.set_locale(code)
    prompt = simulation_api.optimize_interview_prompt("O que acha da medida?")
    assert prompt.startswith(simulation_api.INTERVIEW_PROMPT_PREFIX)
    assert marker in prompt and prompt.rstrip().endswith("O que acha da medida?")
    assert not any("一" <= ch <= "鿿" for ch in simulation_api.INTERVIEW_PROMPT_PREFIX)


def test_interview_prefix_is_not_added_twice():
    once = simulation_api.optimize_interview_prompt("Pergunta")
    assert simulation_api.optimize_interview_prompt(once) == once
    assert simulation_api.optimize_interview_prompt("") == ""
