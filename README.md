<div align="center">

<img src="./frontend/src/assets/logo/noma-mark.svg" alt="Noma" width="120"/>

# Noma

**Motor de inteligência de enxame: envie documentos, descreva o que quer prever e simule o comportamento coletivo de agentes de IA.**

</div>

> Noma é um derivado do projeto open source [MiroFish](https://github.com/666ghj/MiroFish) (AGPL-3.0). Veja [Licença e atribuição](#licença-e-atribuição).

## O que é

A partir de **documentos-semente** (PDF, Markdown ou TXT) e de um **requisito de previsão em linguagem natural**, o Noma:

1. extrai entidades e relações dos documentos e monta um grafo de conhecimento;
2. gera agentes com personas próprias a partir dessas entidades;
3. simula a interação desses agentes em redes sociais (Twitter e Reddit, via [OASIS](https://github.com/camel-ai/oasis));
4. produz um **relatório de previsão** com um agente de relatório que consulta o grafo e a simulação;
5. permite **conversar** com os agentes e com o agente de relatório.

> As simulações são exploratórias e dependem do modelo de linguagem usado. Não trate o resultado como previsão garantida.

## Fluxo na interface

| Etapa | O que acontece |
|---|---|
| 1. Construção do grafo | Extração das sementes e construção do grafo (Zep Cloud) |
| 2. Preparo do ambiente | Geração de personas e da configuração da simulação |
| 3. Simulação | Execução nas plataformas, com acompanhamento de rodadas e ações |
| 4. Relatório | O agente de relatório escreve o relatório por seções |
| 5. Interação | Conversa com agentes simulados e com o agente de relatório |

A interface está disponível em **português, inglês e chinês**. O idioma escolhido também é pedido ao LLM na geração de relatórios.

## Requisitos

| Ferramenta | Versão |
|---|---|
| Node.js | 18+ |
| Python | 3.11 a 3.12 |
| [uv](https://docs.astral.sh/uv/) | recente |
| Conta no [Zep Cloud](https://app.getzep.com/) | chave de API (o projeto só se conecta ao Zep Cloud) |
| Um LLM com API compatível com OpenAI | nuvem ou local (por exemplo, Ollama) |

## Começando

```bash
cp .env.example .env     # preencha as chaves (veja abaixo)
npm run setup:all        # instala dependências do root, frontend e backend
npm run dev              # sobe backend e frontend juntos
```

- Frontend: <http://localhost:3000>
- Backend: <http://127.0.0.1:5001> (por padrão só aceita conexões locais)

Para subir só uma parte: `npm run backend` ou `npm run frontend`.

### Configuração (`.env`)

```env
# LLM (qualquer API compatível com OpenAI)
LLM_API_KEY=...
LLM_BASE_URL=https://...
LLM_MODEL_NAME=...

# Zep Cloud
ZEP_API_KEY=...
```

Opcionais:

| Variável | Para que serve |
|---|---|
| `LLM_SIM_BASE_URL`, `LLM_SIM_MODEL_NAME`, `LLM_SIM_API_KEY` | Modelo dedicado às **ações dos agentes na simulação** (por exemplo, um modelo local), mantendo o LLM geral para ontologia, perfis, configuração e relatório. Ativo quando `LLM_SIM_MODEL_NAME` está definido. |
| `LLM_REASONING_EFFORT`, `LLM_SIM_REASONING_EFFORT` | `none`, `minimal`, `low`, `medium` ou `high`. Com modelos locais que "pensam" (raciocínio oculto), `none` reduz muito o tempo por chamada. |
| `LLM_BOOST_*` | Segundo provedor usado pelo Reddit na simulação paralela. |
| `GRAPH_BACKEND` | Provedor do grafo de conhecimento. Hoje só `zep` (padrão). A camada está isolada em `backend/app/services/graph_backend`, o que permite adicionar outro provedor sem tocar nos serviços. |
| `FLASK_HOST`, `FLASK_PORT` | Endereço e porta do backend (padrão `127.0.0.1:5001`). |

### Idioma do app e das respostas do LLM

O idioma escolhido no seletor (padrão: português) vale para a interface **e** para o que o LLM devolve. Os prompts do backend estão em **inglês**, e cada chamada recebe uma regra de idioma no fim (`get_language_instruction()` para texto livre e `get_json_language_instruction()` para JSON):

- em respostas em JSON, só os **valores de texto legíveis** seguem o idioma; chaves, enums (`male`/`female`, `stance`, `poster_type`) e identificadores continuam em inglês;
- os nomes de tipos de entidade (`PascalCase`) e de relações (`UPPER_SNAKE_CASE`) da ontologia seguem em inglês, mas as **descrições** seguem o idioma escolhido;
- as perguntas de entrevista enviadas aos agentes e o resumo da entrevista também seguem o idioma.

O que **não** muda de idioma, de propósito:

- os rótulos fixos da saída das ferramentas de busca (por exemplo `【关键事实】`, `【核心实体】`, `分析问题:`) e os marcadores `【Twitter平台回答】`/`（该平台未获得回复）`: o `Step4Report` os lê com regex, então mudá-los exige alterar backend e front juntos;
- a **referência de rotina diária da configuração de tempo** continua sendo a da China (UTC+8): é uma suposição de conteúdo, não de idioma;
- as postagens dos agentes na simulação seguem o idioma da persona gerada (o OASIS monta o prompt do agente a partir dela).

### Cadastro e login (front, via Zeep Orbit)

A tela `/auth` tem as abas **Entrar** e **Cadastrar** e fala **direto** com o Orbit (`/{app}/auth/register`, `login`, `refresh`, `me`, `logout`), então a senha não passa pelo backend do Noma. Depois do cadastro a pessoa já entra: o `register` devolve só o token, então o front faz o login em seguida para obter o refresh token.

Variáveis do front (em `frontend/.env`, lidas pelo Vite):

| Variável | Para que serve |
|---|---|
| `VITE_ORBIT_URL` | URL da instância (padrão `https://orbit.dlec.app`). |
| `VITE_ORBIT_APP` | App com login por email ativado (padrão `mirofish`). |
| `VITE_AUTH_REQUIRED` | `false` desliga a exigência de login (uso local). |

Limites que valem conhecer:

- O login sozinho não autoriza ninguém: o `register` do Orbit é público. Quem decide é o **backend**, que confere o token e a lista de emails permitidos (próxima seção).
- O `register` do Orbit é público: qualquer pessoa que conheça a URL cria conta. Se for expor o app, restrinja quem pode se cadastrar.
- A sessão fica em `localStorage`. Se o Orbit estiver fora do ar, a sessão salva continua valendo; só um `401` descarta a sessão.
- Com o login por email ativado, o app **não emite mais token de app**. O espelho de estado (abaixo) entra com um **usuário de serviço** (email e senha), que renova a sessão sozinho.

### Proteção da API (backend)

Todas as rotas `/api/*` exigem `Authorization: Bearer <token>`. O backend não consegue verificar o JWT sozinho (o segredo fica no Orbit), então pergunta ao Orbit quem é o dono do token (`GET /{app}/auth/me`) e só deixa passar emails da lista de permitidos. `OPTIONS` (preflight do CORS) e `/health` ficam abertos.

| Variável | Para que serve |
|---|---|
| `API_AUTH_REQUIRED` | Liga a proteção. Padrão `true`. Use `false` só em desenvolvimento local e **junto** com `VITE_AUTH_REQUIRED=false` no front: valores diferentes quebram o app. |
| `API_ALLOWED_EMAILS` | Emails (separados por vírgula) que podem usar o backend. **Obrigatória** com a proteção ligada: o backend não sobe sem ela (falha fechada). Fica no `.env`, não no repositório. |
| `API_AUTH_CACHE_TTL_SECONDS` | Por quanto tempo uma resposta do Orbit vale (padrão `60`). Evita uma ida ao Orbit por requisição. |

Respostas: `401` sem token ou com token inválido/expirado, `403` se o login é válido mas o email não está na lista, e `503` se o Orbit não responde (sem o Orbit não há como confirmar quem é, então **o app não funciona enquanto o Orbit estiver fora do ar**). O token nunca vai para o log e o cache guarda só o hash.

No front, o axios anexa o token, renova a sessão uma vez ao receber `401` e repete a chamada; em `403` encerra a sessão e mostra o aviso de acesso negado.

### Estado durável no Zeep Orbit (opcional)

Espelha **tarefas** e **checkpoints de etapas** (hoje, o build do grafo) em tabelas do Zeep Orbit, para consultar o histórico e saber onde cada execução parou depois de um reinício. Sem a URL e as credenciais abaixo nada é gravado fora do disco local.

| Variável | Para que serve |
|---|---|
| `ORBIT_BASE_URL` | URL da instância, **sem** `/{app}` no final (por exemplo, `https://orbit.dlec.app`). |
| `ORBIT_APP` | Nome do app (padrão `mirofish`). |
| `ORBIT_SERVICE_EMAIL`, `ORBIT_SERVICE_PASSWORD` | Usuário de serviço do backend (uma conta criada no app, pela tela `/auth`). **Modo recomendado**: o backend faz login e renova a sessão com o refresh token. |
| `ORBIT_API_TOKEN` | **Obsoleto.** Era um token de app; com o RLS `owner` ele não tem dono e o Orbit responde `500`. Use o usuário de serviço. Não use um PAT pessoal. |
| `ORBIT_ORPHAN_GRACE_SECONDS` | Ao subir, tarefas ativas no Orbit sem atualização há mais de N segundos viram `failed (interrupted)`. `0` (padrão) assume um único backend por app. |

Como funciona:

- O disco e a memória continuam sendo a fonte para as decisões do app. O Orbit é um **espelho**: as gravações são assíncronas, com repetição e descarte em caso de falha, então uma indisponibilidade do Orbit nunca interrompe um build.
- O `TaskManager` copia cada mudança de tarefa. O build do grafo grava os checkpoints `chunked → graph_created → ontology_set → ingestion_submitted → ingestion_complete → graph_fetched → completed` (ou `failed`), com IDs e contagens, **sem conteúdo dos documentos**.
- A sessão do usuário de serviço fica só em memória. Ao receber `401`, o cliente renova com `POST /{app}/auth/refresh` e, se o refresh token também não valer mais, faz um novo login. Se o login falhar (senha errada, Orbit fora do ar), ele espera 60 s antes de tentar de novo e as gravações são descartadas com aviso no log, sem afetar o app.
- As tarefas **não** são recarregadas do Orbit para a memória: uma tarefa `processing` restaurada pareceria um build ativo e atrapalharia a retomada existente.

Tabelas do app (RLS em modo `owner`: cada linha só é visível, alterável e apagável por quem a criou, então outra conta cadastrada não enxerga nem sobrescreve o que o backend grava):

- `tasks`: `task_id` (único), `task_type`, `status`, `progress`, `message`, `result`, `error`, `metadata`, `progress_detail` (jsonb), `project_id`, `task_created_at`, `task_updated_at`.
- `steps`: `entity_type`, `entity_id`, `step`, `status`, `seq`, `payload` (jsonb), `error`, `started_at`, `finished_at`, com índice único em `(entity_type, entity_id, step)`.

### Usando um modelo local (exemplo com Ollama)

```env
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL_NAME=<modelo baixado no Ollama>
LLM_API_KEY=ollama
LLM_REASONING_EFFORT=none
```

Modelos locais pequenos podem errar JSON e chamadas de ferramenta, e cada chamada de agente pode levar de dezenas de segundos a minutos. Comece com poucas rodadas (2 a 5) e poucos agentes.

## Diagnóstico e retomada

- A Home mostra um indicador de saúde (LLM, Zep e backend) e avisa na hora quando algo está fora do ar. O mesmo diagnóstico está em `GET /api/system/check`.
- O progresso fica salvo **em disco** (`backend/uploads/`). Se ocorrer um erro e a página for atualizada:
  - a ontologia é refeita a partir dos arquivos já enviados (sem novo upload), com o botão "Continuar de onde parou";
  - o preparo reaproveita a tarefa em andamento e os perfis de agentes já gerados (`profiles_checkpoint.json`).
- Reiniciar o backend interrompe simulações e relatórios em andamento.

## Segurança e privacidade

- A API **não tem autenticação**. Use em máquina local. Se for expor em rede, coloque um proxy autenticado na frente e restrinja o CORS.
- O conteúdo dos documentos é enviado ao **Zep Cloud** e ao **provedor de LLM** configurado. Não envie dados pessoais, de saúde ou confidenciais sem validar contrato, base legal (LGPD) e política de retenção.
- Arquivos enviados, simulações e relatórios ficam em `backend/uploads/` e logs em `backend/logs/` (ambos ignorados pelo Git). Defina uma política de retenção.
- Nunca versione `.env` ou backups com chaves. O `.gitignore` já cobre `.env.*` (exceto `.env.example`) e `*.bak`.

## Docker

O `docker-compose.yml` publica as portas apenas em `127.0.0.1` e define `FLASK_HOST=0.0.0.0` dentro do contêiner. Atenção: o campo `image` do compose aponta para a imagem publicada pelo projeto original (`ghcr.io/666ghj/mirofish`), **não** para este código. Para usar este repositório, construa a imagem a partir do `Dockerfile` e ajuste o `image` do compose. O `Dockerfile` executa os servidores de desenvolvimento, não uma imagem de produção.

## Desenvolvimento

```bash
cd backend && uv run pytest        # testes do backend
cd backend && uvx ruff check app scripts tests
cd frontend && npm run build       # build do frontend
```

O workflow `.github/workflows/ci.yml` roda testes, lint e build a cada push e pull request. Documentação de arquitetura, riscos, decisões e tarefas em [`docs/`](./docs/README.md).

## Licença e atribuição

Este projeto é distribuído sob a **GNU AGPL-3.0** (veja [`LICENSE`](./LICENSE)). Ele é derivado do [MiroFish](https://github.com/666ghj/MiroFish), de seus autores originais, e usa o motor de simulação [OASIS](https://github.com/camel-ai/oasis) da equipe CAMEL-AI. A AGPL exige que, ao disponibilizar uma versão modificada como serviço de rede, o código-fonte correspondente seja oferecido aos usuários. Em caso de uso comercial, valide as obrigações com o jurídico.

A documentação original em chinês está em [`README-ZH.md`](./README-ZH.md).
