import pytest

# Variáveis de ambiente que o .env local pode definir e que alteram o formato das
# requisições ao LLM. Os testes devem ser independentes da configuração do desenvolvedor.
_LLM_TUNING_VARS = (
    "LLM_REASONING_EFFORT",
    "LLM_SIM_REASONING_EFFORT",
    "LLM_SIM_API_KEY",
    "LLM_SIM_BASE_URL",
    "LLM_SIM_MODEL_NAME",
)


@pytest.fixture(autouse=True)
def _isolate_llm_tuning_env(monkeypatch):
    for name in _LLM_TUNING_VARS:
        monkeypatch.delenv(name, raising=False)


# O .env do desenvolvedor pode ter credenciais reais do Orbit. Sem isto, qualquer
# teste que cria uma tarefa (TaskManager) gravaria no Orbit de verdade. Cada teste
# começa com o espelho desligado; os testes do state_store ligam o que precisam.
_ORBIT_CONFIG_ATTRS = (
    "ORBIT_BASE_URL",
    "ORBIT_API_TOKEN",
    "ORBIT_SERVICE_EMAIL",
    "ORBIT_SERVICE_PASSWORD",
)


@pytest.fixture(autouse=True)
def _isolate_orbit_state_store(monkeypatch):
    from app.config import Config
    from app.services import state_store
    from app.services.state_store.null import NullStateStore

    for name in _ORBIT_CONFIG_ATTRS:
        monkeypatch.setattr(Config, name, "")
    state_store.reset_state_store(NullStateStore())
    yield
    state_store.reset_state_store(None)


# A proteção da API vem ligada por padrão. Os testes de rotas existentes não enviam
# token, então ela começa desligada em todo teste; test_api_auth.py liga o que precisa.
@pytest.fixture(autouse=True)
def _api_auth_off_by_default(monkeypatch):
    from app.config import Config
    from app.utils import api_auth

    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", False)
    monkeypatch.setattr(Config, "API_ALLOWED_EMAILS", ())
    api_auth.reset_for_tests(None)
    yield
    api_auth.reset_for_tests(None)


# O locale é thread-local e persistia entre testes (um teste que escolhia "zh" mudava as
# mensagens do próximo). Cada teste começa e termina no idioma padrão.
@pytest.fixture(autouse=True)
def _reset_locale():
    from app.utils import locale as locale_utils

    locale_utils.set_locale(locale_utils.DEFAULT_LOCALE)
    yield
    locale_utils.set_locale(locale_utils.DEFAULT_LOCALE)
