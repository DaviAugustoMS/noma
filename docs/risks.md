# Project Risks

> Análise estática em 2026-10-05. Itens são riscos/preocupações potenciais, não vulnerabilidades confirmadas, salvo indicação.

## Critical

_Nenhum identificado com evidência suficiente._

## High

- [~] API sem autenticação/autorização, com CORS aberto e bind em todas as interfaces
  - Mitigado em 2026-10-05 para uso local: bind padrão `127.0.0.1` (`run.py`), portas do compose em loopback, proxy do Vite em `127.0.0.1`. Autenticação e CORS restrito seguem pendentes (necessários se exposto em rede).
  - Severity: High (se exposto fora de localhost); Low em uso local
  - Evidence: `backend/app/__init__.py` (`CORS(... origins "*")`), `backend/run.py` (`FLASK_HOST` padrão `0.0.0.0`), `docker-compose.yml` (porta 5001 publicada), ausência de qualquer checagem de auth em `backend/app/api/`
  - Impact: qualquer cliente na rede lê/apaga projetos, simulações, relatórios; consome créditos de LLM/Zep do dono da chave (DoS financeiro).
  - Recommendation: bind em 127.0.0.1 por padrão; token/API key simples ou proxy autenticado se exposto.

- [x] Stack trace devolvido ao cliente
  - Verified: 0 ocorrências de `"traceback"` em `backend/app/api`; traceback agora vai para `logger.error`; handler global JSON sem detalhes em `app/__init__.py`; `test_security_hardening.py`. `str(e)` ainda é devolvido nas rotas com try/except próprio (aceitável para uso local).
- (histórico) Stack trace e mensagem de exceção devolvidos ao cliente
  - Severity: High/Medium (potential security concern: vazamento de caminhos, versões, trechos de config)
  - Evidence: `traceback.format_exc()` na resposta JSON em `backend/app/api/graph.py:838,903` e padrão repetido (~51 ocorrências de `traceback` em `backend/app/api/*.py`; `str(e)` em ~177)
  - Impact: exposição de detalhes internos.
  - Recommendation: logar no servidor; devolver mensagem genérica + id de correlação; `traceback` só com `DEBUG`.

- [x] CI não executa testes nem lint
  - Verified: `.github/workflows/ci.yml` (pytest + ruff + build do frontend). Ainda não executado no GitHub.
- (histórico) CI não executa testes nem lint
  - Severity: High (manutenibilidade)
  - Evidence: `.github/workflows/` só tem `docker-image.yml` (build em tag) e `update-star-history.yml`
  - Impact: regressões nos 18 arquivos de teste passam despercebidas.
  - Recommendation: job `uv sync && uv run pytest` em PR.

## Medium

- [x] Possível path traversal por IDs não validados
  - Verified: validação `^[A-Za-z0-9_-]{1,128}$` em rotas e corpo JSON (`app/__init__.py`), testes em `test_security_hardening.py`.
- (histórico) Possível path traversal por `simulation_id`/`project_id` não validados
  - Severity: Medium (potential security concern, não explorado)
  - Evidence: `backend/app/api/simulation.py:289,1099,1207` (`os.path.join(OASIS_SIMULATION_DATA_DIR, simulation_id)`); `simulation_manager.py:154`. O conversor `<simulation_id>` do Flask não aceita `/`, mas aceita `..`; rotas de DELETE de projeto/relatório merecem verificação.
  - Impact: acesso/remoção fora do diretório esperado.
  - Recommendation: validar IDs por regex (`^[A-Za-z0-9_-]+$`) e conferir `realpath` dentro da base.
  - Verification required: ler rotas DELETE em `graph.py`/`report.py`.

- [ ] `SECRET_KEY` com valor padrão público
  - Evidence: `backend/app/config.py:21` (`'mirofish-secret-key'`)
  - Impact: baixo hoje (não se observou uso de sessões/cookies assinados), mas vira risco se sessões forem adicionadas.
  - Recommendation: exigir via env fora de modo debug.

- [x] Log DEBUG registra corpo das requisições
  - Verified: corpo removido do log em `app/__init__.py`.
- (histórico) Log DEBUG registra corpo das requisições
  - Evidence: `backend/app/__init__.py:57` (`request.get_json(silent=True)`)
  - Impact: com `FLASK_DEBUG=true`/log em DEBUG, conteúdo de documentos e requisitos (potencialmente dados pessoais/confidenciais) vai para `backend/logs/`.
  - Recommendation: truncar/mascarar; não logar corpo.

- [ ] Dados de usuário persistidos sem retenção definida
  - Evidence: `backend/uploads/{projects,reports,simulations}`, volume montado no compose
  - Impact: documentos-semente e relatórios acumulam em disco; relevância LGPD se houver dados pessoais.
  - Recommendation: política de retenção/limpeza; documentar.

- [ ] Imagem Docker executa servidores de desenvolvimento (Flask `app.run`, `vite --host`) e usa `latest`
  - Evidence: `Dockerfile` (`CMD ["npm","run","dev"]`), `docker-compose.yml` (`ghcr.io/666ghj/mirofish:latest`)
  - Impact: não adequado para exposição pública; builds não reproduzíveis.
  - Recommendation: Gunicorn/uvicorn + build estático do frontend; fixar tag/digest.

- [ ] Arquivos monolíticos de alta complexidade
  - Evidence: `frontend/src/components/Step4Report.vue` (5162 linhas), `backend/app/api/simulation.py` (2878), `report_agent.py` (2619)
  - Impact: alto custo de mudança e de revisão; risco de regressão.

- [ ] Estado de simulação em memória do processo
  - Evidence: `simulation_runner.py:229` (`_processes: Dict`)
  - Impact: reinício do backend perde controle de subprocessos; múltiplos workers dessincronizam.

## Low

- [ ] Dependência de serviços pagos/externos sem fallback (Zep Cloud, LLM) — evidência em `config.py` (`validate`).
- [ ] `.env.openai.bak` com credenciais em texto no diretório do projeto (ignorado via `.git/info/exclude`, não rastreado). Risco apenas de vazamento acidental (backup, zip, sync em nuvem). Recomendação: remover/rotacionar e mover para cofre de segredos.
- [ ] Duplicidade de manifestos Python (`pyproject.toml`/`uv.lock` vs `requirements.txt`) pode divergir.
- [ ] `languages.json` anuncia 7 idiomas, mas só 3 arquivos de locale existem (es, fr, ru, de ausentes) — risco de seletor mostrar idioma sem tradução. Verificar fallback.
- [ ] Licença AGPL-3.0: uso como serviço de rede obriga disponibilizar código-fonte modificado; validar com jurídico antes de uso comercial/Starbem.

## Resolved

_Nenhum._
