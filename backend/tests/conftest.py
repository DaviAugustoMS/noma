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
