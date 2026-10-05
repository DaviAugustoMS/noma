# Architecture

## System Overview

Aplicação web de duas partes: backend Flask (API REST + orquestração) e SPA Vue 3. Simulações rodam em subprocessos Python separados (scripts em `backend/scripts/`), comunicando-se com o backend por arquivos/IPC. Estado persistido em disco (`backend/uploads/`), grafos no Zep Cloud.
> Status: Confirmed

## Architecture Style

Monólito em camadas (api → services → models/utils), sem evidência de adoção formal de Clean/Hexagonal. Processamento longo com tasks (`models/task.py`, rotas `/api/graph/task/<id>` e `/prepare/status`) consultadas por polling; rotas `*/stream` em `report` sugerem SSE. Mecanismo interno de execução das tasks (threads/armazenamento): não verificado.
> Status: Inferred from implementation. Adesão a algum padrão formal: Not confirmed.

## Repository Structure

```
backend/app/api        blueprints: graph, simulation, report
backend/app/services   13 módulos (report_agent, simulation_runner, zep_*, ontology_generator, ...)
backend/app/models     project, task
backend/app/utils      llm_client, file_parser, locale, logger, retry, zep_paging
backend/scripts        scripts executados em subprocesso (twitter/reddit/parallel) + validações
backend/tests          18 arquivos pytest
frontend/src           views(7), components(8), api(4), router, store, i18n
locales/               en, zh, pt (+ languages.json) — compartilhado por front e back
scripts/ tests/        utilitários de Star History (não ligados ao produto)
.github/workflows      docker-image.yml, update-star-history.yml
```

## Application Layers

Presentation (Vue) → HTTP (axios) → `api/*` (validação, i18n via `t()`) → `services/*` (lógica) → Zep Cloud / LLM / subprocessos / disco.

## Modules

- `graph`: projeto, upload, ontologia, build de grafo (assíncrono com task).
- `simulation`: entidades, create/prepare, geração de perfis/config, start/stop, status/ações/timeline, entrevistas.
- `report`: geração, status, logs (agent/console, com stream), chat, tools de busca/estatística.

## Components

`SimulationRunner` (processos, cleanup no shutdown), `SimulationManager`, `ReportAgent`, `ZepTools`, `GraphBuilderService`, `OasisProfileGenerator`, `SimulationConfigGenerator`, `OntologyGenerator`, `ZepGraphMemoryUpdater`, `simulation_ipc`.

## Data Flow

Upload → texto (PyMuPDF/charset-normalizer) → chunking (500/50) → ontologia (LLM) → grafo (Zep) → entidades → perfis+config (LLM) → subprocesso OASIS → logs/actions em disco → Zep memory updater → Report Agent → relatório em disco.

## State Management

Frontend: Vue + `store/pendingUpload.js` (store simples). Backend: arquivos JSON em `uploads/` + estruturas em memória (`SimulationRunner._processes`).
> Implicação: estado em memória não é compartilhado entre workers/instâncias.

## API Architecture

REST JSON sob `/api/{graph,simulation,report}`, respostas `{success, data|error}`. 59 rotas. `/health` fora do prefixo. Sem versionamento, sem OpenAPI.

## Database

Sem banco relacional. Persistência em sistema de arquivos + Zep Cloud (grafo/memória).

## Authentication

Não implementada.

## Authorization

Não implementada. Qualquer cliente com acesso à rede acessa/exclui projetos, simulações e relatórios.

## External Integrations

OpenAI-compatible LLM, Zep Cloud (`zep-cloud==3.25.0`), OASIS (`camel-oasis==0.2.5`, `camel-ai==0.2.78`).

## Infrastructure

`Dockerfile` (python:3.11 + apt nodejs/npm, uv 0.9.26) executa `npm run dev` (Flask + Vite em modo dev). `docker-compose.yml` usa imagem `ghcr.io/666ghj/mirofish:latest`, portas 3000/5001, volume `backend/uploads`.

## Deployment

Somente via Docker/dev server. Não há build de produção servido (frontend roda `vite --host`).

## CI/CD

`docker-image.yml`: build multi-arch (amd64/arm64) e push para GHCR em tags. **Sem job de lint/teste.** `update-star-history.yml` condicionado a `666ghj/MiroFish`.

## Observability

Logger próprio (`utils/logger.py`), arquivos diários em `backend/logs/`. `/health` simples. Sem métricas/tracing.

## Error Handling

`try/except Exception` por rota retornando `str(e)` e, em ~51 pontos de `api/`, também `traceback` na resposta (ver `risks.md`). Retry com backoff existe em `utils/retry.py` (não referenciado).

## Security

Ver `risks.md`.

## Performance

Gargalos prováveis: chamadas LLM/Zep sequenciais, simulações em subprocesso, polling. Nenhuma medição disponível.
> Status: Unknown

## Testing Strategy

pytest em `backend/tests` (foco em contratos Zep, JSON de LLM, ontologia, barreiras de simulação/relatório). `tests/` na raiz cobre Star History. **Frontend sem testes; CI não roda testes.** Execução e cobertura não verificadas.

## Dependency Strategy

Backend: `pyproject.toml` + `uv.lock` (fonte do Docker) e `requirements.txt` paralelo (36 linhas). Frontend: npm, deps mínimas (vue 3.5, vue-router, vue-i18n 11, axios, d3, vite 7).

## Architectural Decisions

- Zep Cloud-only (validação explícita contra `ZEP_API_URL`).
- i18n compartilhado via `locales/*.json` (back: `utils/locale.py`; front: `import.meta.glob`).

## Known Architectural Debt

- Arquivos gigantes: `Step4Report.vue` 5162 linhas, `api/simulation.py` 2878, `report_agent.py` 2619, `Step2EnvSetup.vue` 2623, `Step5Interaction.vue` 2584, `simulation_runner.py` 2033.
- Estado em memória + disco; sem fila de jobs.
- Sem camada de auth.

## Open Architectural Questions

- Uso previsto é single-user local ou serviço multiusuário?
- `requirements.txt` ainda é mantido?
- `languages.json` lista es/fr/ru/de sem arquivos de locale: comportamento de fallback no front/back?
