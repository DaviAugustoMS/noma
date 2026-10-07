"""Contagem de tokens do LLM por projeto e por etapa (gasto total).

Cada chamada ao LLM (``LLMClient``) registra o ``usage`` da resposta no escopo ativo
(projeto + etapa). O escopo é um ``ContextVar``: o hook de requisição o preenche e as
threads criadas pelo backend o herdam via ``in_context``. O que não tem escopo vai para
``SEM_PROJETO``, então o total geral nunca perde chamadas.

A simulação OASIS roda em outro processo; ele grava ``llm_usage.json`` na pasta da
simulação (``scripts/usage_meter.py``) e este módulo soma esse arquivo na leitura.

O livro-razão é um JSON por projeto em ``uploads/usage/`` (escrita atômica). Só guarda
contadores: nunca o conteúdo dos prompts nem das respostas.
"""

from __future__ import annotations

import contextvars
import json
import os
import re
import threading
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from ..config import Config

SEM_PROJETO = "_sem_projeto"
STAGES = ("seed", "ontology", "prepare", "simulation", "report", "chat", "interviews", "other")
_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,80}$")

_scope: contextvars.ContextVar[tuple[str, str] | None] = contextvars.ContextVar("mirofish_usage_scope", default=None)
_captures: contextvars.ContextVar[tuple["Totals", ...]] = contextvars.ContextVar("mirofish_usage_captures", default=())
_lock = threading.Lock()


class Totals:
    """Acumulador simples (também usado para devolver o gasto de uma única requisição)."""

    def __init__(self) -> None:
        self.prompt = 0
        self.completion = 0
        self.calls = 0
        self.estimated_calls = 0

    @property
    def total(self) -> int:
        return self.prompt + self.completion

    def as_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt,
            "completion_tokens": self.completion,
            "total_tokens": self.total,
            "calls": self.calls,
            "estimated_calls": self.estimated_calls,
        }


def _dir() -> str:
    path = os.path.join(Config.UPLOAD_FOLDER, "usage")
    os.makedirs(path, exist_ok=True)
    return path


def _safe_id(value: str) -> str:
    return value if _ID_RE.match(value or "") else SEM_PROJETO


def _ledger_path(project_id: str) -> str:
    return os.path.join(_dir(), f"{_safe_id(project_id)}.json")


# ---------------------------------------------------------------- escopo

def bind(project_id: str | None, stage: str) -> None:
    """Define o escopo da requisição/thread atual."""

    _scope.set((_safe_id(project_id or ""), stage if stage in STAGES else "other"))


def current_scope() -> tuple[str, str]:
    return _scope.get() or (SEM_PROJETO, "other")


def in_context(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Envolve ``fn`` para rodar com o escopo de hoje (use ao criar threads/executors)."""

    ctx = contextvars.copy_context()

    def runner(*args: Any, **kwargs: Any) -> Any:
        return ctx.run(fn, *args, **kwargs)

    return runner


@contextmanager
def capture() -> Iterator[Totals]:
    """Soma tudo que for registrado dentro do bloco (para devolver na própria resposta)."""

    totals = Totals()
    token = _captures.set(_captures.get() + (totals,))
    try:
        yield totals
    finally:
        _captures.reset(token)


# ---------------------------------------------------------------- escrita

def _empty() -> dict[str, Any]:
    return {"stages": {}}


def _load(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) and isinstance(data.get("stages"), dict) else _empty()
    except (OSError, ValueError):
        return _empty()


def add(project_id: str, stage: str, prompt: int, completion: int, *, estimated: bool = False) -> None:
    """Soma ao livro-razão do projeto. Valores inválidos viram 0 (nunca negativos)."""

    prompt, completion = max(0, int(prompt or 0)), max(0, int(completion or 0))
    stage = stage if stage in STAGES else "other"
    for totals in _captures.get():
        totals.prompt += prompt
        totals.completion += completion
        totals.calls += 1
        totals.estimated_calls += 1 if estimated else 0
    path = _ledger_path(project_id)
    with _lock:
        data = _load(path)
        row = data["stages"].setdefault(
            stage, {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0, "estimated_calls": 0}
        )
        row["prompt_tokens"] += prompt
        row["completion_tokens"] += completion
        row["calls"] += 1
        row["estimated_calls"] += 1 if estimated else 0
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
        os.replace(tmp, path)


def move_seed(project_id: str, prompt: int, completion: int, calls: int) -> None:
    """Passa o gasto da semente (gerada antes de o projeto existir) para o projeto, sem contar duas vezes.

    Os números vêm do cliente, então ficam limitados ao que a semente "sem projeto" realmente tem.
    """

    path = _ledger_path(SEM_PROJETO)
    with _lock:
        data = _load(path)
        seed = data["stages"].get("seed")
        if not seed:
            return
        prompt = min(max(0, int(prompt or 0)), seed["prompt_tokens"])
        completion = min(max(0, int(completion or 0)), seed["completion_tokens"])
        calls = min(max(0, int(calls or 0)), seed["calls"])
        seed["prompt_tokens"] -= prompt
        seed["completion_tokens"] -= completion
        seed["calls"] -= calls
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
        os.replace(tmp, path)
    target = _ledger_path(project_id)
    with _lock:
        data = _load(target)
        row = data["stages"].setdefault(
            "seed", {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0, "estimated_calls": 0}
        )
        row["prompt_tokens"] += prompt
        row["completion_tokens"] += completion
        row["calls"] += calls
        tmp = f"{target}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
        os.replace(tmp, target)


def _estimate(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def record_response(response: Any, messages: list[dict[str, Any]] | None = None) -> None:
    """Registra o consumo de uma resposta do LLM. Nunca levanta (contar não pode quebrar a chamada)."""

    try:
        project_id, stage = current_scope()
        usage = getattr(response, "usage", None)
        prompt = getattr(usage, "prompt_tokens", None)
        completion = getattr(usage, "completion_tokens", None)
        if prompt is None and completion is None:
            text_in = "".join(str(m.get("content", "")) for m in (messages or []))
            choices = getattr(response, "choices", None) or []
            message = getattr(choices[0], "message", None) if choices else None
            text_out = str(getattr(message, "content", "") or "")
            add(project_id, stage, _estimate(text_in), _estimate(text_out), estimated=True)
        else:
            add(project_id, stage, prompt or 0, completion or 0)
    except Exception:  # noqa: BLE001
        return


# ---------------------------------------------------------------- leitura

def _simulation_usage(project_id: str) -> dict[str, int] | None:
    """Soma o ``llm_usage.json`` das simulações do projeto (processo separado)."""

    from ..services.simulation_manager import SimulationManager

    prompt = completion = calls = 0
    found = False
    manager = SimulationManager()
    for state in manager.list_simulations(project_id):
        path = os.path.join(manager.SIMULATION_DATA_DIR, state.simulation_id, "llm_usage.json")
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        found = True
        prompt += int(data.get("prompt_tokens", 0) or 0)
        completion += int(data.get("completion_tokens", 0) or 0)
        calls += int(data.get("calls", 0) or 0)
    return {"prompt_tokens": prompt, "completion_tokens": completion, "calls": calls, "estimated_calls": 0} if found else None


def _cost(prompt: int, completion: int) -> float | None:
    price_in, price_out = Config.LLM_PRICE_INPUT_PER_1M, Config.LLM_PRICE_OUTPUT_PER_1M
    if not (price_in or price_out):
        return None
    return round(prompt / 1_000_000 * price_in + completion / 1_000_000 * price_out, 6)


def _finish(stages: dict[str, dict[str, int]]) -> dict[str, Any]:
    prompt = sum(s["prompt_tokens"] for s in stages.values())
    completion = sum(s["completion_tokens"] for s in stages.values())
    out_stages = {}
    for name, row in stages.items():
        total = row["prompt_tokens"] + row["completion_tokens"]
        out_stages[name] = {**row, "total_tokens": total, "cost": _cost(row["prompt_tokens"], row["completion_tokens"])}
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
        "calls": sum(s["calls"] for s in stages.values()),
        "estimated_calls": sum(s.get("estimated_calls", 0) for s in stages.values()),
        "cost": _cost(prompt, completion),
        "currency": Config.LLM_PRICE_CURRENCY if (Config.LLM_PRICE_INPUT_PER_1M or Config.LLM_PRICE_OUTPUT_PER_1M) else None,
        "stages": out_stages,
    }


def project_usage(project_id: str) -> dict[str, Any]:
    with _lock:
        stages = _load(_ledger_path(project_id))["stages"]
    stages = {k: dict(v) for k, v in stages.items()}
    sim = _simulation_usage(project_id) if _safe_id(project_id) != SEM_PROJETO else None
    if sim:
        stages["simulation"] = sim
    return _finish(stages)


def all_usage() -> dict[str, Any]:
    """Gasto total de todos os projetos (inclui chamadas sem projeto)."""

    merged: dict[str, dict[str, int]] = {}
    try:
        names = [n[:-5] for n in os.listdir(_dir()) if n.endswith(".json")]
    except OSError:
        names = []
    for name in names:
        for stage, row in project_usage(name)["stages"].items():
            into = merged.setdefault(
                stage, {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0, "estimated_calls": 0}
            )
            for key in into:
                into[key] += int(row.get(key, 0) or 0)
    return _finish(merged)
