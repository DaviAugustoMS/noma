"""Conta os tokens das chamadas ao LLM feitas pela simulação (processo separado).

O backend define ``MIROFISH_USAGE_FILE``; aqui trocamos ``create`` do SDK OpenAI por um
wrapper que soma ``response.usage`` e grava os totais nesse arquivo (sem conteúdo de
prompts). Continua de onde o arquivo parou se a simulação for retomada.
"""

import atexit
import json
import os
import threading
import time

_state = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
_lock = threading.Lock()
_installed = False
_last_flush = 0.0


def _flush(force: bool = False) -> None:
    global _last_flush
    path = os.environ.get("MIROFISH_USAGE_FILE", "")
    now = time.monotonic()
    if not path or (not force and now - _last_flush < 1.0):
        return
    _last_flush = now
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(_state, handle)
        os.replace(tmp, path)
    except OSError:
        pass


def _count(response) -> None:
    usage = getattr(response, "usage", None)
    with _lock:
        _state["calls"] += 1
        _state["prompt_tokens"] += int(getattr(usage, "prompt_tokens", 0) or 0)
        _state["completion_tokens"] += int(getattr(usage, "completion_tokens", 0) or 0)
        _flush()


def install() -> None:
    """Idempotente; sem ``MIROFISH_USAGE_FILE`` não faz nada."""

    global _installed
    path = os.environ.get("MIROFISH_USAGE_FILE", "")
    if _installed or not path:
        return
    _installed = True
    try:
        with open(path, "r", encoding="utf-8") as handle:
            previous = json.load(handle)
        for key in _state:
            _state[key] = int(previous.get(key, 0) or 0)
    except (OSError, ValueError):
        pass

    from openai.resources.chat.completions import AsyncCompletions, Completions

    original_sync, original_async = Completions.create, AsyncCompletions.create

    def sync_create(self, *args, **kwargs):
        response = original_sync(self, *args, **kwargs)
        _count(response)
        return response

    async def async_create(self, *args, **kwargs):
        response = await original_async(self, *args, **kwargs)
        _count(response)
        return response

    Completions.create = sync_create
    AsyncCompletions.create = async_create
    atexit.register(lambda: _flush(force=True))
