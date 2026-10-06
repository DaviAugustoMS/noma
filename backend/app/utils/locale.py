import json
import os
import threading
from flask import request, has_request_context

_thread_local = threading.local()

# Idioma padrão quando a requisição/thread não informa um válido.
DEFAULT_LOCALE = 'pt'

_locales_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'locales')

# Load language registry
with open(os.path.join(_locales_dir, 'languages.json'), 'r', encoding='utf-8') as f:
    _languages = json.load(f)

# Load translation files
_translations = {}
for filename in os.listdir(_locales_dir):
    if filename.endswith('.json') and filename != 'languages.json':
        locale_name = filename[:-5]
        with open(os.path.join(_locales_dir, filename), 'r', encoding='utf-8') as f:
            _translations[locale_name] = json.load(f)


def set_locale(locale: str):
    """Set locale for current thread. Call at the start of background threads."""
    _thread_local.locale = locale


def get_locale() -> str:
    if has_request_context():
        raw = request.headers.get('Accept-Language', DEFAULT_LOCALE)
        return raw if raw in _translations else DEFAULT_LOCALE
    return getattr(_thread_local, 'locale', DEFAULT_LOCALE)


def t(key: str, **kwargs) -> str:
    locale = get_locale()
    messages = _translations.get(locale, _translations.get(DEFAULT_LOCALE, {}))

    value = messages
    for part in key.split('.'):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = None
            break

    if value is None:
        value = _translations.get(DEFAULT_LOCALE, {})
        for part in key.split('.'):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
                break

    if value is None:
        return key

    if kwargs:
        for k, v in kwargs.items():
            value = value.replace(f'{{{k}}}', str(v))

    return value


def get_language_instruction() -> str:
    """Instrução de idioma para respostas em texto livre (relatórios, conversas)."""
    locale = get_locale()
    lang_config = _languages.get(locale, _languages.get(DEFAULT_LOCALE, {}))
    return lang_config.get('llmInstruction', 'IMPORTANT: Write the entire response in Brazilian Portuguese.')


def get_language_name() -> str:
    """Nome do idioma selecionado, em inglês (para prompts em inglês)."""
    locale = get_locale()
    lang_config = _languages.get(locale, _languages.get(DEFAULT_LOCALE, {}))
    return lang_config.get('llmLanguage', 'Brazilian Portuguese')


def get_json_language_instruction() -> str:
    """Instrução de idioma para respostas em JSON.

    Só os valores de texto legíveis por pessoas seguem o idioma selecionado; chaves,
    enums, nomes de campo e identificadores ficam exatamente como o schema pede.
    """
    return (
        f"LANGUAGE RULE: write every human-readable text value in {get_language_name()}. "
        "Keep JSON keys, enum values, field names and identifiers exactly as specified in the "
        "schema (they stay in English), even when the examples or instructions are in another language."
    )
