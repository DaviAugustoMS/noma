# Engineering Rules

> Adaptadas ao que o repositório já pratica. Regras marcadas (*) são recomendação, não prática observada.

## General

- Seguir padrões existentes (blueprints Flask + services; respostas `{success, ...}`).
- Não adicionar dependência sem justificativa; avaliar existente equivalente, manutenção, segurança, licença (projeto é AGPL-3.0).
- Não duplicar lógica de negócio; extrair para `services/` ou `utils/`.
- Não alterar contratos de API sem checar consumidores em `frontend/src/api/*.js`.

## Python (backend)

- Python 3.11–3.12 (`requires-python`). Gerenciar com `uv` (`uv.lock` é a fonte).
- Mensagens ao usuário via `t('chave')` (`utils/locale.py`); nada de string fixa em um só idioma. (Observado: comentários e logs em chinês.)
- Config só em `app/config.py`; segredos só por env.
- (*) Não retornar `traceback` nem `str(e)` bruto ao cliente.
- (*) Validar IDs de rota (`simulation_id`, `project_id`, `report_id`) antes de compor caminhos.

## Frontend (Vue 3)

- Textos via `vue-i18n` + `locales/*.json`; toda nova chave deve existir em todos os locales (en/zh/pt hoje têm paridade de chaves de topo).
- (*) Componentes novos < ~500 linhas; extrair subcomponentes.

## Testing

- Lógica de negócio e integrações novas exigem pytest em `backend/tests` (padrão: mocks do Zep/LLM).
- Bug fix deve incluir teste de regressão quando viável.
- (*) CI deve rodar `uv run pytest`.

## Segredos e dados

- `.env` nunca no Git (coberto por `.gitignore`); arquivos `*.bak` com chaves devem ficar fora do repositório.
- Uploads em `backend/uploads` podem conter dados de terceiros: não versionar nem logar conteúdo.

## i18n

- Novo idioma = novo `locales/<code>.json` + entrada em `languages.json`.

## Git

- Commits no estilo Conventional Commits (histórico: `chore: ...`). Status: Inferred.
