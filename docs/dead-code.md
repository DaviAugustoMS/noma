# Dead Code

> Busca estática. "Sem referências" não implica segurança para remover.

## Candidates

- [ ] `backend/app/utils/retry.py` (`retry_with_backoff`, `retry_with_backoff_async`, `RetryableAPIClient`)
  - Evidence: nenhuma importação em `backend/app`, `backend/scripts`, `backend/tests` (grep por `utils.retry`, `retry_with_backoff`, `RetryableAPIClient`); não exportado em `utils/__init__.py`. Existe `test_zep_retry_and_client.py`, que deve ser conferido (pode implementar retry próprio).
  - Confidence: Medium
  - Action: verificar uso dinâmico e consumidores externos antes de remover; alternativamente, adotá-lo no tratamento de erros de LLM/Zep.

- [x] `backend/scripts/test_profile_format.py` NÃO é código morto
  - Verified: pytest o coleta e executa (`scripts/test_profile_format.py::test_profile_formats`). Não mover sem ajustar a coleta.

- [ ] `requirements.txt` (backend)
  - Evidence: Dockerfile e `package.json` usam `uv sync`/`uv.lock`; `pyproject.toml` é a fonte.
  - Confidence: Low/Medium
  - Action: confirmar se algum fluxo (README) ainda usa pip.

- [ ] Dependências possivelmente redundantes: `chardet` (fallback de `charset-normalizer`), `pipreqs` em extra `dev`
  - Confidence: Low
  - Action: validar necessidade; `httpx` tem 1 import.

## Checked, no candidates found

- Componentes/views Vue: todos os 8 componentes e 7 views têm ao menos uma referência.
- Módulos de `services/` e `models/`: todos referenciados.

## Resolved

_Nenhum._
