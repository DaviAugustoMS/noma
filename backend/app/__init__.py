"""
MiroFish Backend - Flask应用工厂
"""

import os
import re
import warnings

# Suprime avisos do resource_tracker do multiprocessing (vindos de bibliotecas de terceiros como transformers)
# Precisa ser configurado antes de todas as outras importações
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from .config import Config
from .utils.logger import setup_logger, get_logger

_SAFE_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,128}$')
_BODY_ID_KEYS = ('simulation_id', 'project_id', 'report_id', 'graph_id', 'task_id')


def create_app(config_class=Config):
    """Flask应用工厂函数"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Configura a codificação JSON: garante que o chinês seja exibido diretamente (e não no formato \uXXXX)
    # Flask >= 2.3 usa app.json.ensure_ascii; versões antigas usam a configuração JSON_AS_ASCII
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # Configura o log
    logger = setup_logger('mirofish')
    
    # Imprime informações de inicialização apenas no subprocesso do reloader (evita imprimir duas vezes no modo debug)
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish Backend iniciando...")
        logger.info("=" * 50)
    
    # Habilita CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Registra a função de limpeza de processos de simulação (garante que todos os processos de simulação sejam encerrados quando o servidor for desligado)
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("Função de limpeza de processos de simulação registrada")
    
    # Espelho durável (Orbit): fecha tarefas que o processo anterior deixou ativas.
    if should_log_startup:
        from .services.state_store import is_state_store_configured, reconcile_orphan_tasks

        if is_state_store_configured():
            import threading

            def _reconcile_orphans():
                try:
                    reconcile_orphan_tasks()
                except Exception as error:  # nunca impede o servidor de subir
                    get_logger('mirofish.state_store').warning(
                        "Falha ao reconciliar tarefas órfãs: %s", type(error).__name__
                    )

            threading.Thread(target=_reconcile_orphans, daemon=True,
                             name="StateStoreReconcile").start()

    # Proteção da API: exige o token do usuário (validado no Orbit) em /api/*.
    # OPTIONS passa (preflight do CORS não leva credenciais) e /health fica aberto.
    @app.before_request
    def require_api_auth():
        if not app.config.get('API_AUTH_REQUIRED', Config.API_AUTH_REQUIRED):
            return None
        if request.method == 'OPTIONS' or not request.path.startswith('/api/'):
            return None
        from .utils.api_auth import AuthFailure, authenticate
        try:
            g.current_user_email = authenticate(request.headers.get('Authorization'))
        except AuthFailure as failure:
            response = jsonify({"success": False, "error": failure.message, "code": failure.code})
            response.status_code = failure.status
            if failure.status == 401:
                response.headers['WWW-Authenticate'] = 'Bearer'
            return response
        return None

    # Escopo do gasto de tokens (projeto + etapa) das rotas que chamam o LLM.
    @app.before_request
    def bind_usage_scope():
        from .api.usage import bind_request_scope
        return bind_request_scope()

    # Middleware de log de requisições
    @app.before_request
    def validate_route_ids():
        # IDs gerados pelo backend usam apenas [A-Za-z0-9_-]; recusa "..", "." etc.
        # antes de qualquer os.path.join com o ID.
        for key, value in (request.view_args or {}).items():
            if key.endswith('_id') and not _SAFE_ID_RE.match(str(value)):
                return jsonify({"success": False, "error": f"Invalid {key}"}), 400
        body = request.get_json(silent=True) if request.is_json else None
        if isinstance(body, dict):
            for key in _BODY_ID_KEYS:
                value = body.get(key)
                if isinstance(value, str) and value and not _SAFE_ID_RE.match(value):
                    return jsonify({"success": False, "error": f"Invalid {key}"}), 400

    @app.before_request
    def log_request():
        logger = get_logger('mirofish.request')
        # Não loga o corpo: pode conter documentos e dados pessoais do usuário.
        logger.debug(f"Requisição: {request.method} {request.path}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"Resposta: {response.status_code}")
        return response
    
    # Registra os blueprints
    from .api import graph_bp, simulation_bp, report_bp, system_bp, usage_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(system_bp, url_prefix='/api/system')
    app.register_blueprint(usage_bp, url_prefix='/api/usage')
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        # Rotas sem try/except próprio: loga no servidor e devolve JSON sem detalhes internos.
        if isinstance(error, HTTPException):
            return error
        get_logger('mirofish.request').exception("Unhandled error on %s %s", request.method, request.path)
        return jsonify({"success": False, "error": "Internal server error"}), 500

    # Verificação de saúde
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFish Backend'}
    
    if should_log_startup:
        logger.info("MiroFish Backend iniciado")
    
    return app

