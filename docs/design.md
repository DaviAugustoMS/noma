# Design

> Análise do frontend limitada a estrutura; estilos (CSS dentro dos `.vue`) não foram auditados.

## Design System

Status: Not established.

O projeto não possui design system formalmente documentado nem biblioteca de componentes (dependências de UI: apenas `d3` para visualização de grafo).

## Brand

Logo em `static/image/` e `frontend/src/assets/logo`. Sem guia de marca no repo.

## Typography / Colors / Spacing

Unknown. Definidos localmente em CSS de cada componente (a verificar).

## Components

`GraphPanel` (d3), `HistoryDatabase`, `LanguageSwitcher`, `Step1GraphBuild`…`Step5Interaction`. Views: Home, Process, MainView, SimulationView, SimulationRunView, ReportView, InteractionView.

## Layout / Responsive Behavior

Unknown.

## Accessibility

Not verified.

## Interaction Patterns

Fluxo em 5 passos; polling para tarefas longas; streams SSE para logs de relatório.

## Navigation

`vue-router` (`frontend/src/router/index.js`).

## Forms / Empty / Loading / Error States

Not verified. Textos de estado vêm de `locales/*.json` (`common.loading`, `common.error`, `common.noData`, …).

## Platform Differences

Somente web desktop (inferido); `vite --host` expõe na rede local.

## Design References

Nenhuma.

## Known Design Debt

- Componentes de 2–5 mil linhas misturam template, lógica e estilo.
- Sem tokens de design compartilhados (a verificar).
