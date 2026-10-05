# Product Requirements Document

> Derivado da implementação e do README. Itens sem marcação são **Inferred from implementation**.

## Product

MiroFish: motor de "inteligência de enxame" que, a partir de documentos-semente (PDF/MD/TXT) e de um requisito de previsão em linguagem natural, constrói um mundo digital paralelo com agentes de IA, simula interação social (Twitter/Reddit via OASIS) e gera um relatório de previsão, com possibilidade de interagir/entrevistar os agentes.
> Status: Confirmed (README)

## Problem

Prever trajetórias de eventos (opinião pública, políticas, sinais financeiros) simulando comportamento coletivo em vez de modelos estatísticos tradicionais.
> Status: Confirmed (README, "Our Vision")

## Vision

"Ensaiar o futuro" em um sandbox digital antes de decidir. Ver README.

## Objectives

- Pipeline guiado em 5 passos na UI: construir grafo → configurar ambiente → simular → relatório → interação (`Step1GraphBuild` … `Step5Interaction`).
> Status: Inferred from implementation

## Non-Goals

> Status: Requires confirmation (não documentado).

## Users

Analistas/tomadores de decisão que sobem materiais e descrevem o objetivo de previsão. Sem noção de contas/papéis no código.
> Status: Inferred from implementation

## User Personas

> Status: Requires confirmation.

## Core Use Cases

1. Upload de seed + requisito → geração de ontologia → construção de grafo de conhecimento (Zep Cloud).
2. Leitura de entidades do grafo → geração de perfis de agentes → geração de configuração de simulação (LLM).
3. Execução de simulação Twitter/Reddit/paralela em subprocesso, com acompanhamento (status, ações, timeline, stats).
4. Geração de relatório por "Report Agent" (ferramentas sobre o grafo) e chat com o relatório.
5. Entrevista de agentes individualmente/em lote/todos.
6. Histórico de projetos/simulações/relatórios; download de configs, scripts e relatórios.
7. Interface multilíngue (zh, en, pt; `languages.json` declara também es, fr, ru, de).

## Functional Requirements

Ver 59 rotas em `backend/app/api/{graph,simulation,report}.py` (resumo em `Architecture.md`).

## Non-Functional Requirements

- Upload máx. 50 MB; extensões `pdf, md, txt, markdown` (`backend/app/config.py`).
- Simulações longas e consumo alto de LLM (aviso no `.env.example`: testar com <40 rodadas).
> Status: Confirmed. Demais NFRs (latência, disponibilidade, escala): Unknown.

## Business Rules

- Sem regras de negócio de domínio além do pipeline; limites de rodadas por `OASIS_DEFAULT_MAX_ROUNDS` (10), Report Agent: `MAX_TOOL_CALLS=5`, `MAX_REFLECTION_ROUNDS=2`.

## Integrations

- LLM via SDK OpenAI (qualquer provider compatível; padrão sugerido: Alibaba Bailian/qwen-plus).
- Zep Cloud (grafo/memória). `ZEP_API_URL` explicitamente não suportado.
- OASIS / camel-ai (simulação social).
- Opcional: LLM "boost" (`LLM_BOOST_*`).

## Constraints

- Python >=3.11,<3.13; Node >=18; apenas Zep Cloud; AGPL-3.0 (obrigações de código aberto em uso em rede).

## MVP Scope

Versão `v0.1-Preview` (UI) — pipeline completo acima.

## Future Scope

> Status: Requires confirmation.

## Acceptance Criteria

> Status: Unknown. Não há critérios formais; cobertura de testes só no backend (ver `Architecture.md`).

## Open Questions

- Existe público-alvo multiusuário? (hoje não há autenticação.)
- Qual o plano de deploy além do Docker em modo dev?
- Qual a política de retenção dos dados em `backend/uploads` (podem conter documentos de terceiros)?

## Decisions

Nenhuma decisão formal registrada. Ver `memory.md`.
