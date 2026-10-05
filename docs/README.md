# Project Documentation — MiroFish

## Status

ACTIVE (fork/clone local do projeto open source `666ghj/MiroFish`, AGPL-3.0)

## Project Mode

EXISTING PROJECT

## Documentation

- [PRD](./PRD.md)
- [Architecture](./Architecture.md)
- [Rules](./rules.md)
- [Design](./design.md)
- [Tasks](./task.md)
- [Memory](./memory.md)
- [Risks](./risks.md)
- [Improvements](./improvements.md)
- [Duplication](./duplication.md)
- [Dead Code](./dead-code.md)

## Maintenance

Esta documentação deve permanecer sincronizada com a implementação.

- Antes de mudanças arquiteturais, revisar `Architecture.md`.
- Antes de nova funcionalidade, revisar `PRD.md`, `rules.md`, `task.md` e `memory.md`.
- Antes de limpeza técnica, revisar `risks.md`, `improvements.md`, `duplication.md`, `dead-code.md`.

## Analysis Metadata

- Última análise: 2026-10-05
- Commit analisado: `7657031` (+ `locales/pt.json` não rastreado)
- Método: análise estática (leitura + grep). **Testes não foram executados** nesta análise.
- Última revisão de arquitetura: 2026-10-05

## Warnings

- Esta análise é estática; nenhum item de `dead-code.md` foi validado dinamicamente.
- Arquivos `.env` e `.env.openai.bak` existem localmente com credenciais; não foram lidos nem documentados aqui.
