# Code Duplication

> Análise limitada a padrões observados por grep e leitura parcial; sem ferramenta de clones.

## Active

- [ ] Tratamento de erro repetido por rota (`except Exception` → `jsonify({success:False,error:str(e),traceback:...})`)
  - Evidence: ~51 ocorrências de `traceback` em `backend/app/api/*.py` (ex.: `graph.py:838,903`, `simulation.py` download de script)
  - Impact: High (corrigir vazamento exige tocar dezenas de pontos)
  - Recommendation: handler central de erros.

- [ ] Três scripts de simulação com estrutura sobreposta
  - Evidence: `backend/scripts/run_twitter_simulation.py` (780), `run_reddit_simulation.py` (769), `run_parallel_simulation.py` (1699), `action_logger.py`
  - Impact: Medium
  - Verification required: comparar blocos de setup/IPC/logging antes de consolidar; plataformas podem diferir de forma intencional.

- [ ] Resolução de `os.path.join(OASIS_SIMULATION_DATA_DIR, simulation_id)` repetida
  - Evidence: `api/simulation.py:289,1099,1207` e `simulation_manager._get_simulation_dir`
  - Impact: Low/Medium (também é ponto único para validar ID)
  - Recommendation: usar sempre `SimulationManager._get_simulation_dir` (com validação).

- [ ] Dupla lógica de detecção de encoding
  - Evidence: `utils/file_parser.py` usa `charset_normalizer` com fallback `chardet`; ambos declarados em `pyproject.toml`.
  - Impact: Low. Pode ser intencional (fallback).

## Not verified

- Componentes `Step*.vue` e `Process.vue` provavelmente repetem lógica de polling/formatação; não analisado em profundidade.

## Resolved

_Nenhum._
