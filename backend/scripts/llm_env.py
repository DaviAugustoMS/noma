"""
Seleção da configuração de LLM usada pelos scripts de simulação.

Precedência (da maior para a menor):
1. LLM_SIM_*    - modelo dedicado às ações dos agentes (ex.: modelo local via Ollama).
                  Ativo quando LLM_SIM_MODEL_NAME está definido.
2. LLM_BOOST_*  - somente quando prefer_boost=True e LLM_BOOST_API_KEY existe.
3. LLM_*        - configuração geral.

Somente as simulações usam LLM_SIM_*; ontologia, perfis, config e relatório
continuam usando LLM_* (ver backend/app/config.py).
"""

import os
from typing import Any, Dict, Tuple

# Valor exigido pelo SDK OpenAI quando o endpoint local não usa autenticação.
_LOCAL_PLACEHOLDER_KEY = "not-needed"


def resolve_llm_settings(
    config: Dict[str, Any], prefer_boost: bool = False
) -> Tuple[str, str, str, str]:
    """Retorna (api_key, base_url, model, label) sem alterar o ambiente."""
    env = os.environ
    sim_model = env.get("LLM_SIM_MODEL_NAME", "").strip()

    if sim_model:
        base_url = env.get("LLM_SIM_BASE_URL", "").strip() or env.get("LLM_BASE_URL", "")
        api_key = env.get("LLM_SIM_API_KEY", "").strip()
        if not api_key:
            # Chave geral só é reutilizada se o endpoint for o mesmo da configuração geral.
            if base_url == env.get("LLM_BASE_URL", ""):
                api_key = env.get("LLM_API_KEY", "")
            else:
                api_key = _LOCAL_PLACEHOLDER_KEY
        return api_key, base_url, sim_model, "[SIM LLM]"

    if prefer_boost and env.get("LLM_BOOST_API_KEY", ""):
        model = env.get("LLM_BOOST_MODEL_NAME", "") or env.get("LLM_MODEL_NAME", "")
        return (
            env.get("LLM_BOOST_API_KEY", ""),
            env.get("LLM_BOOST_BASE_URL", ""),
            model or config.get("llm_model", "gpt-4o-mini"),
            "[加速LLM]",
        )

    model = env.get("LLM_MODEL_NAME", "") or config.get("llm_model", "gpt-4o-mini")
    return (
        env.get("LLM_API_KEY", ""),
        env.get("LLM_BASE_URL", ""),
        model,
        "[通用LLM]",
    )


_VALID_REASONING_EFFORT = {"none", "minimal", "low", "medium", "high"}


def resolve_reasoning_effort():
    """LLM_SIM_REASONING_EFFORT > LLM_REASONING_EFFORT; valores inválidos são ignorados."""
    for name in ("LLM_SIM_REASONING_EFFORT", "LLM_REASONING_EFFORT"):
        value = os.environ.get(name, "").strip().lower()
        if value in _VALID_REASONING_EFFORT:
            return value
    return None


def create_simulation_model(config: Dict[str, Any], prefer_boost: bool = False):
    """Cria o modelo camel-ai (plataforma OpenAI-compatível) para uma simulação."""
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType

    api_key, base_url, model, label = resolve_llm_settings(config, prefer_boost)

    # Conta os tokens da simulação (o backend define MIROFISH_USAGE_FILE); sem a variável não faz nada.
    from usage_meter import install as install_usage_meter

    install_usage_meter()

    # camel-ai lê estas variáveis ao criar o modelo
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key

    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("缺少 API Key 配置，请在项目根目录 .env 文件中设置 LLM_API_KEY")

    if base_url:
        os.environ["OPENAI_API_BASE_URL"] = base_url

    # Não imprime a chave; a URL é truncada como antes.
    print(f"{label} model={model}, base_url={base_url[:40] if base_url else '默认'}...")

    kwargs = {}
    effort = resolve_reasoning_effort()
    if effort:
        from camel.configs import ChatGPTConfig

        kwargs["model_config_dict"] = ChatGPTConfig(reasoning_effort=effort).as_dict()

    return ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI,
        model_type=model,
        **kwargs,
    )
