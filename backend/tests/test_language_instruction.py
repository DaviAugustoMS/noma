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
