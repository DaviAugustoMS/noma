# Project Memory

## Current State

Clone local de `666ghj/MiroFish` v0.1.0 (commit `7657031`, 1 commit no histórico local). Única mudança local: `locales/pt.json` (novo, não rastreado; 667 linhas, mesmas chaves de topo que `en.json`).

## Important Decisions

- Zep Cloud-only: `Config.validate()` rejeita `ZEP_API_URL`.
- LLM via formato OpenAI com `LLM_BASE_URL` configurável.

## Important Constraints

- Python >=3.11,<3.13; Node >=18; AGPL-3.0.
- Upload máx. 50 MB, extensões pdf/md/txt/markdown.
- Simulações consomem muito LLM: testar com poucas rodadas.

## Established Patterns

- Simulações usam `backend/scripts/llm_env.py`: precedência `LLM_SIM_*` > `LLM_BOOST_*` (só Reddit no modo paralelo) > `LLM_*`. Ontologia/perfis/config/relatório seguem em `LLM_*`.
- Validação de IDs em `app/__init__.py` (`[A-Za-z0-9_-]`); IDs gerados: `proj_`, `sim_`, `report_`, `mirofish_`, uuid de task.

- Blueprints Flask (`/api/graph|simulation|report`), resposta `{success, data|error}`.
- Mensagens via `t()` e `locales/*.json` compartilhados por front e back.
- Simulação em subprocesso (`backend/scripts/run_*_simulation.py`).

- Reasoning de modelos locais: `LLM_REASONING_EFFORT=none` (backend) e `LLM_SIM_REASONING_EFFORT` (simulações) evitam milhares de tokens ocultos; o `.env` local usa Ollama em `127.0.0.1:11435` (`qwen3.5-nothink`, ~10 tok/s), que precisa estar rodando.
- `GET /api/system/check` informa estado do LLM/Zep (cache 15s); a Home exibe chip e aviso.
- Scripts de simulação compartilham `backend/scripts/sim_common.py` e `llm_env.py`; todos gravam `<plataforma>/actions.jsonl`. Execuções com `max_rounds` começam na primeira hora ativa dos agentes.
- O processo de simulação permanece vivo (modo espera de entrevistas) após `*_completed`; o status final só muda quando o processo termina (`/stop` ou fechar o ambiente).

- Retomada após erro: perfis de agentes são gravados em `<simulação>/profiles_checkpoint.json` (só os gerados com sucesso; descartado com `force_regenerate`); `/api/simulation/prepare` reaproveita a tarefa em andamento (`resumed: true`) e `/prepare/status` por `simulation_id` devolve o progresso real; `POST /api/graph/ontology/retry` refaz a ontologia a partir dos arquivos salvos. Em `MainView`, falha de ontologia leva ao projeto salvo e há botão "Continuar de onde parou".
- Idioma do LLM: `locales/languages.json` (`llmInstruction`) é anexado aos prompts de sistema e, no relatório, também ao fim das mensagens do usuário; modelos locais tendem a seguir o idioma chinês dos prompts. Mudanças nesse arquivo exigem reiniciar o backend.
- Cuidado operacional: reiniciar o backend interrompe simulações/relatórios em andamento (estado de processos em memória).

- Marca: o produto agora se chama **Noma** na interface (Home, cabeçalhos, título da aba, textos en/pt/zh, `meta.title`), com logo "N" em `frontend/src/assets/logo/noma-mark.svg` e favicon `frontend/public/favicon.svg`. Internamente (loggers, `/health`, pacotes, pasta) o nome MiroFish permanece. Repositório: `github.com/DaviAugustoMS/noma`. Código derivado do MiroFish (AGPL-3.0): manter `LICENSE` e crédito ao projeto original.

- Relatórios órfãos: a geração roda em thread do backend; ao reiniciar, `ReportManager.mark_interrupted_reports()` (chamado em `run.py`, nunca em `create_app`/testes) marca como `failed` os que estavam pending/planning/generating, preservando as seções escritas. `ReportView` mostra aviso e botão "Gerar novamente" (`force_regenerate`).

## Forbidden Patterns

- Commitar `.env` (ignorado). Não ler/expor conteúdo de `.env` e `.env.openai.bak`.

## Known Exceptions

- `scripts/` e `tests/` da raiz tratam de Star History do repositório upstream, não do produto.

## Historical Context

Projeto upstream chinês; README em en/zh; comentários majoritariamente em chinês.

## Previous Problems

Nenhum registrado.

## Integration Notes

- `languages.json` define 7 idiomas, mas só en/zh/pt têm arquivo.
- `docker-compose.yml` usa imagem upstream `ghcr.io/666ghj/mirofish:latest`, não build local.

## Operational Notes

- Dev: `npm run setup:all` e `npm run dev` (front 3000, back 5001).
- Logs diários em `backend/logs/`; dados em `backend/uploads/`.

## Agent Notes

- Análise de 2026-10-05 foi estática; testes não rodados.
- Contexto Starbem: este projeto não faz parte do stack Starbem conhecido; confirmar o objetivo do uso antes de investir em mudanças.

## Things That Must Not Be Forgotten

- API sem auth: não expor `0.0.0.0` em rede não confiável.
- Chaves reais existem em arquivos locais ignorados pelo Git.
