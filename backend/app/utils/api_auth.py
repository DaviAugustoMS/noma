"""Proteção das rotas /api/*: valida o token do usuário no Zeep Orbit.

O backend não consegue verificar o JWT sozinho (o segredo fica no Orbit), então
pergunta ao Orbit quem é o dono do token (``GET /{app}/auth/me``) e só deixa
passar emails da lista de permitidos. Como o ``register`` do Orbit é público,
"token válido" não significa "autorizado": a lista é o que autoriza.

Falha fechada: sem token ou token inválido -> 401; email fora da lista -> 403;
Orbit indisponível -> 503 (sem Orbit não há como confirmar quem é).
O token nunca é registrado em log nem mantido em claro (o cache usa o hash).
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from typing import Callable

import httpx

from ..config import Config
from .locale import t

_TIMEOUT = httpx.Timeout(5.0, connect=3.0)
_NEGATIVE_TTL_SECONDS = 30.0  # tokens inválidos: evita martelar o Orbit com lixo


class AuthFailure(Exception):
    """Falha de autenticação/autorização, já com o status HTTP e a mensagem."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@dataclass
class _Entry:
    email: str | None  # None = token recusado pelo Orbit
    expires_at: float


class _MeCache:
    """Cache limitado por hash do token, com TTL."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._items: dict[str, _Entry] = {}

    def get(self, key: str) -> _Entry | None:
        with self._lock:
            entry = self._items.get(key)
            if entry and entry.expires_at > self._clock():
                return entry
            self._items.pop(key, None)
            return None

    def put(self, key: str, email: str | None, ttl: float) -> None:
        with self._lock:
            limit = max(1, Config.API_AUTH_CACHE_MAX)
            if len(self._items) >= limit:
                now = self._clock()
                for stale in [k for k, e in self._items.items() if e.expires_at <= now]:
                    del self._items[stale]
                while len(self._items) >= limit:  # ainda cheio: descarta o mais antigo
                    self._items.pop(next(iter(self._items)))
            self._items[key] = _Entry(email, self._clock() + ttl)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


_cache = _MeCache()
_client: httpx.Client | None = None


def _http() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=_TIMEOUT)
    return _client


def reset_for_tests(client: httpx.Client | None = None) -> None:
    """Zera cache e troca o cliente HTTP (apenas testes)."""

    global _client
    _client = client
    _cache.clear()


def allowed_emails() -> frozenset[str]:
    return frozenset(e.strip().lower() for e in Config.API_ALLOWED_EMAILS if e.strip())


def _token_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _lookup_email(token: str) -> str | None:
    """Pergunta ao Orbit quem é o dono do token. ``None`` = token recusado."""

    url = f"{Config.ORBIT_BASE_URL.rstrip('/')}/{Config.ORBIT_APP}/auth/me"
    try:
        response = _http().get(url, headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError:
        raise AuthFailure(503, "auth_unavailable", t("err.authUnavailable")) from None
    if response.status_code == 401:
        return None
    if response.status_code != 200:
        raise AuthFailure(503, "auth_unavailable", t("err.authUnavailable"))
    try:
        email = str(response.json().get("email") or "").strip().lower()
    except ValueError:
        raise AuthFailure(503, "auth_unavailable", t("err.authUnavailable")) from None
    if not email:
        raise AuthFailure(503, "auth_unavailable", t("err.authUnavailable"))
    return email


def authenticate(authorization_header: str | None) -> str:
    """Devolve o email autenticado e autorizado, ou levanta ``AuthFailure``."""

    scheme, _, token = (authorization_header or "").partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise AuthFailure(401, "auth_required", t("err.authRequired"))

    key = _token_key(token)
    entry = _cache.get(key)
    if entry is None:
        email = _lookup_email(token)  # 503 não é guardado em cache
        ttl = max(1.0, float(Config.API_AUTH_CACHE_TTL_SECONDS)) if email else _NEGATIVE_TTL_SECONDS
        _cache.put(key, email, ttl)
        entry = _cache.get(key) or _Entry(email, 0.0)

    if entry.email is None:
        raise AuthFailure(401, "auth_invalid", t("err.authInvalid"))
    if entry.email not in allowed_emails():
        raise AuthFailure(403, "auth_forbidden", t("err.authForbidden"))
    return entry.email


def config_errors() -> list[str]:
    """Erros de configuração quando a proteção está ligada (para Config.validate)."""

    if not Config.API_AUTH_REQUIRED:
        return []
    errors: list[str] = []
    if not Config.ORBIT_BASE_URL:
        errors.append("API_AUTH_REQUIRED exige ORBIT_BASE_URL (o Orbit confirma quem é o dono do token)")
    if not allowed_emails():
        errors.append(
            "API_AUTH_REQUIRED exige API_ALLOWED_EMAILS (lista de emails separados por vírgula); "
            "sem ela ninguém teria acesso"
        )
    return errors
