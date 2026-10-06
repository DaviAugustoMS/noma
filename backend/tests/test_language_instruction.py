import pytest

from app.utils import locale as locale_utils


@pytest.mark.parametrize("code,marker", [
    ("pt", "português"),
    ("en", "English"),
    ("es", "español"),
    ("fr", "français"),
    ("de", "Deutsch"),
    ("ru", "русском"),
])
def test_instruction_is_explicit_and_in_the_selected_language(code, marker):
    locale_utils.set_locale(code)
    text = locale_utils.get_language_instruction()
    assert marker in text
    assert len(text) > 60  # instrução completa, não só "responda em X"


def test_portuguese_is_the_default_and_unknown_locale_falls_back_to_it():
    locale_utils.set_locale("zh")
    assert "中文" in locale_utils.get_language_instruction()  # zh continua disponível
    locale_utils.set_locale("xx")
    assert "português" in locale_utils.get_language_instruction()  # desconhecido -> padrão


@pytest.mark.parametrize("code,name", [
    ("pt", "Brazilian Portuguese"), ("en", "English"), ("zh", "Simplified Chinese"),
    ("es", "Spanish"), ("fr", "French"), ("de", "German"), ("ru", "Russian"),
])
def test_json_instruction_names_the_language_and_protects_schema_fields(code, name):
    locale_utils.set_locale(code)
    text = locale_utils.get_json_language_instruction()
    assert name in text and locale_utils.get_language_name() == name
    # só valores de texto mudam de idioma; chaves/enums/identificadores ficam como o schema pede
    for must in ("JSON keys", "enum values", "identifiers"):
        assert must in text
    assert not any("一" <= ch <= "鿿" for ch in text)   # a regra em si é em inglês


def test_unknown_locale_uses_the_default_language_for_the_json_rule():
    locale_utils.set_locale("xx")
    assert "Brazilian Portuguese" in locale_utils.get_json_language_instruction()


def test_chinese_instruction_is_strong_and_still_contains_the_marker():
    locale_utils.set_locale("zh")
    text = locale_utils.get_language_instruction()
    assert "中文" in text and "Simplified Chinese" in text and len(text) > 80
