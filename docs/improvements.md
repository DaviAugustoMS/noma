# Improvements

> Melhorias não são defeitos. Prioridade por impacto/esforço.

## Architecture

- [ ] Quebrar `api/simulation.py` (2878 linhas, ~30 rotas) em módulos por responsabilidade (entidades, preparo, execução, entrevistas).
- [ ] Extrair um handler de erro central (`@app.errorhandler`) para substituir os `try/except Exception` repetidos por rota.
- [ ] Definir contrato de API (OpenAPI) — hoje 59 rotas sem especificação.

## Performance

- [ ] Medir tempo de chamadas LLM/Zep e avaliar paralelismo na geração de perfis. (Sem dados atuais.)

## Developer Experience

- [ ] Adicionar linter/formatter (ruff para Python; eslint/prettier para Vue). Nenhum configurado.
- [ ] Unificar manifestos Python (manter só `pyproject.toml`/`uv.lock` ou gerar `requirements.txt`).
- [ ] Script/README para rodar testes (`uv run pytest`).

## Testing

- [ ] Rodar a suíte pytest e registrar baseline (não executada nesta análise).
- [ ] Testes de frontend (vitest) para `api/*` e store.
- [ ] Teste de segurança para validação de IDs de rota.

## Security

- [ ] Auth mínima (API key) e bind local por padrão. Ver `risks.md`.
- [ ] Remover `traceback` das respostas.
- [ ] Rotacionar e remover `.env.openai.bak`.

## Maintainability

- [ ] Dividir `Step4Report.vue`, `Step2EnvSetup.vue`, `Step5Interaction.vue`, `Process.vue`.
- [ ] Padronizar idioma de comentários/logs (hoje majoritariamente chinês) ou documentar a convenção.

## UX

- [ ] Verificar fallback para idiomas declarados sem locale (es, fr, ru, de) ou removê-los de `languages.json`.

## Infrastructure

- [ ] Imagem de produção (servidor WSGI + build estático) e tag fixa no compose.
- [ ] CI com testes em PR; cache de uv/npm.

## Documentation

- [ ] Validar PRD com quem conhece o produto (itens "Requires confirmation").
- [ ] Decidir se `locales/pt.json` (hoje não rastreado) será commitado; paridade de chaves de topo com `en.json` verificada, paridade profunda não.
