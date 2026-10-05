"""
Diagnóstico de dependências externas (LLM e Zep Cloud).

A UI consulta este endpoint para avisar imediatamente quando o servidor de LLM
local está desligado ou a chave do Zep não está configurada, em vez de deixar o
usuário esperando uma requisição longa que vai falhar.
"""

import threading
import time
from typing import Any, Dict
from urllib.parse import urlparse

import httpx
from flask import jsonify

from . import system_bp
from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.system')

_CACHE_TTL_SECONDS = 15
_PROBE_TIMEOUT_SECONDS = 3.0
_ZEP_URL = "https://api.getzep.com"

_cache_lock = threading.Lock()
_cache: Dict[str, Any] = {"at": 0.0, "value": None}


def _classify_http_error(error: Exception) -> str:
    if isinstance(error, httpx.ConnectError):
        return "connection_refused"
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    return "error"


def _check_llm() -> Dict[str, Any]:
    base_url = (Config.LLM_BASE_URL or "").rstrip("/")
    parsed = urlparse(base_url)
    # host:porta é seguro para exibir; chaves nunca saem daqui
    endpoint = f"{parsed.hostname or '?'}" + (f":{parsed.port}" if parsed.port else "")
    result: Dict[str, Any] = {
        "configured": bool(Config.LLM_API_KEY and base_url),
        "endpoint": endpoint,
        "model": Config.LLM_MODEL_NAME,
        "reachable": False,
        "latency_ms": None,
        "reason": None,
    }
    if not result["configured"]:
        result["reason"] = "not_configured"
        return result

    started = time.monotonic()
    try:
        response = httpx.get(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {Config.LLM_API_KEY}"},
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
        if response.status_code in (401, 403):
            result["reason"] = "unauthorized"
        elif response.status_code >= 500:
            result["reason"] = "server_error"
        else:
            # 404 em /models existe em alguns provedores compatíveis: o servidor respondeu
            result["reachable"] = True
    except Exception as error:
        result["reason"] = _classify_http_error(error)
    return result


def _check_zep() -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "configured": bool(Config.ZEP_API_KEY),
        "reachable": False,
        "latency_ms": None,
        "reason": None,
    }
    if not result["configured"]:
        result["reason"] = "not_configured"
        return result

    started = time.monotonic()
    try:
        httpx.get(_ZEP_URL, timeout=_PROBE_TIMEOUT_SECONDS)
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
        result["reachable"] = True
    except Exception as error:
        result["reason"] = _classify_http_error(error)
    return result


def run_system_check(use_cache: bool = True) -> Dict[str, Any]:
    now = time.monotonic()
    with _cache_lock:
        if use_cache and _cache["value"] is not None and now - _cache["at"] < _CACHE_TTL_SECONDS:
            return _cache["value"]

    llm = _check_llm()
    zep = _check_zep()
    value = {"ok": bool(llm["reachable"] and zep["reachable"]), "llm": llm, "zep": zep}

    with _cache_lock:
        _cache["at"] = now
        _cache["value"] = value
    return value


@system_bp.route('/check', methods=['GET'])
def system_check():
    """GET /api/system/check — estado do LLM e do Zep (cache de 15s)."""
    return jsonify({"success": True, "data": run_system_check()})
