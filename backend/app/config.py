"""\n配置管理\n统一从项目根目录的 .env 文件加载配置\n"""

import os
from dotenv import load_dotenv

# Carrega o arquivo .env da raiz do projeto
# Caminho: MiroFish/.env (relativo a backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # Se não houver .env na raiz, tenta carregar as variáveis de ambiente (para ambiente de produção)
    load_dotenv(override=True)


class Config:
    """Flask配置类"""
    
    # Configuração do Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Configuração de JSON - desabilita o escape ASCII, para que o chinês seja exibido diretamente
    JSON_AS_ASCII = False
    
    # Configuração do LLM (formato OpenAI de forma unificada)
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    
    # Configuração do Zep
    # Knowledge-graph provider (see app/services/graph_backend). Only 'zep' today.
    GRAPH_BACKEND = os.environ.get('GRAPH_BACKEND', 'zep')
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')

    # Espelho durável do estado (tarefas e checkpoints) no Zeep Orbit. Opcional:
    # sem ORBIT_BASE_URL e credenciais nada é gravado fora do disco local.
    ORBIT_BASE_URL = os.environ.get('ORBIT_BASE_URL', '').strip()
    ORBIT_APP = os.environ.get('ORBIT_APP', 'mirofish').strip()
    # Usuário de serviço (login por email/senha no app do Orbit). É o modo
    # recomendado: renova a sessão sozinho. ORBIT_API_TOKEN é só um fallback
    # legado, que não pode ser renovado.
    ORBIT_SERVICE_EMAIL = os.environ.get('ORBIT_SERVICE_EMAIL', '').strip()
    ORBIT_SERVICE_PASSWORD = os.environ.get('ORBIT_SERVICE_PASSWORD', '')
    ORBIT_API_TOKEN = os.environ.get('ORBIT_API_TOKEN', '').strip()
    # Ao subir, tarefas ativas no Orbit sem atualização há mais de N segundos
    # viram "failed (interrupted)". 0 = sempre (um único backend por app).
    ORBIT_ORPHAN_GRACE_SECONDS = int(os.environ.get('ORBIT_ORPHAN_GRACE_SECONDS', '0'))

    # Proteção das rotas /api/*: valida o token do usuário no Orbit (GET /auth/me) e
    # só deixa passar emails da lista. Ligada por padrão; use API_AUTH_REQUIRED=false
    # em desenvolvimento local (e VITE_AUTH_REQUIRED=false no front, os dois juntos).
    API_AUTH_REQUIRED = os.environ.get('API_AUTH_REQUIRED', 'true').strip().lower() != 'false'
    API_ALLOWED_EMAILS = tuple(
        e.strip().lower() for e in os.environ.get('API_ALLOWED_EMAILS', '').split(',') if e.strip()
    )
    API_AUTH_CACHE_TTL_SECONDS = int(os.environ.get('API_AUTH_CACHE_TTL_SECONDS', '60'))
    API_AUTH_CACHE_MAX = int(os.environ.get('API_AUTH_CACHE_MAX', '256'))
    
    # Configuração de upload de arquivos
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # Configuração de processamento de texto
    DEFAULT_CHUNK_SIZE = 500  # Tamanho padrão de chunk
    DEFAULT_CHUNK_OVERLAP = 50  # Tamanho padrão de sobreposição
    
    # Configuração da simulação OASIS
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # Configuração das ações disponíveis nas plataformas OASIS
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Configuração do Report Agent
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    @classmethod
    def validate(cls) -> list[str]:
        """验证必要配置"""
        errors: list[str] = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY não configurada")
        graph_backend = (cls.GRAPH_BACKEND or "zep").strip().lower()
        if graph_backend != "zep":
            errors.append(f"GRAPH_BACKEND {graph_backend!r} não é suportado; valores aceitos: zep")
        elif not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY não configurada")
        if os.environ.get("ZEP_API_URL"):
            errors.append("ZEP_API_URL não é suportada; o MiroFish só conecta ao Zep Cloud")
        if cls.DEBUG:
            import warnings
            warnings.warn("Flask DEBUG mode is enabled. Do not use in production.", RuntimeWarning)
        from .utils.api_auth import config_errors

        errors.extend(config_errors())
        return errors
