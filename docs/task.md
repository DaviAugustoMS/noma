# Tasks

## Current Sprint

- [x] Rodar `uv run pytest` em `backend/` e registrar baseline
  - Verified: 144 passed (2026-10-05, após as mudanças).

## High Priority

- [x] Remover `traceback` das respostas de erro e centralizar o tratamento
  - Priority: P1 · Related: `risks.md`, `duplication.md`
- [x] Bind padrão em `127.0.0.1` (uso local confirmado pelo usuário). Auth por token só se for exposto em rede.
  - Priority: Related: `risks.md`
- [x] Adicionar job de testes ao CI (ci.yml; falta primeira execução no GitHub)
  - Priority: P1 · Related: `risks.md`
- [ ] Rotacionar chaves em `.env.openai.bak` e removê-lo da pasta
  - Priority: P1 · Ação do dono das chaves (conteúdo não foi lido).

## Medium Priority

- [x] Validar IDs de rota e corpo (regex)
  - Priority: P2 · Verification: ler rotas DELETE
- [x] Parar de logar corpo de requisição em DEBUG
  - Priority: P2
- [ ] Definir retenção de `backend/uploads`
  - Priority: P2
- [ ] Decidir sobre `locales/pt.json` (não rastreado) e idiomas declarados sem arquivo
  - Priority: P2

## Low Priority

- [ ] Unificar `requirements.txt` e `pyproject.toml`
  - Priority: P3
- [ ] Imagem Docker de produção e tag fixa
  - Priority: P3

## Technical Debt

- [ ] Dividir `api/simulation.py` (cuidado: testes fazem monkeypatch em `app.api.simulation.*`; migrar testes junto)
- [ ] (original) Dividir `api/simulation.py`, `report_agent.py`, `Step4Report.vue`, `Step2EnvSetup.vue`, `Step5Interaction.vue`
- [ ] Decidir destino de `utils/retry.py` (adotar ou remover) — ver `dead-code.md`

## Documentation

- [ ] Validar PRD ("Requires confirmation") com responsáveis
- [ ] Validar licença AGPL-3.0 com jurídico antes de uso comercial

## Completed

- [x] Pipeline validado de ponta a ponta com LLM local (ontologia 128s, grafo ~20s, preparo ~4m30 para 5 entidades, simulação 2 rodadas ~70s) em 2026-10-05
- [x] Scripts de uma plataforma passaram a registrar `actions.jsonl` e fim de simulação (Twitter 9 ações, Reddit 7 verificados)
- [x] Relógio de simulação curta começa na primeira hora ativa; rodadas vazias são logadas
- [x] `GET /api/system/check` + aviso na Home (LLM/Zep/backend)

- [x] Geração inicial de `docs/` (2026-10-05)
