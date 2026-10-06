"""
MiroFish Backend - Flask应用工厂
"""

import os
import re
import warnings

# 抑制 multiprocessing resource_tracker 的警告（来自第三方库如 transformers）
# 需要在所有其他导入之前设置
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
    
    # 设置JSON编码：确保中文直接显示（而不是 \uXXXX 格式）
    # Flask >= 2.3 使用 app.json.ensure_ascii，旧版本使用 JSON_AS_ASCII 配置
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # 设置日志
    logger = setup_logger('mirofish')
    
    # 只在 reloader 子进程中打印启动信息（避免 debug 模式下打印两次）
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish Backend 启动中...")
        logger.info("=" * 50)
    
    # 启用CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # 注册模拟进程清理函数（确保服务器关闭时终止所有模拟进程）
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("已注册模拟进程清理函数")
    
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

    # 请求日志中间件
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
        logger.debug(f"请求: {request.method} {request.path}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"响应: {response.status_code}")
        return response
    
    # 注册蓝图
    from .api import graph_bp, simulation_bp, report_bp, system_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(system_bp, url_prefix='/api/system')
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        # Rotas sem try/except próprio: loga no servidor e devolve JSON sem detalhes internos.
        if isinstance(error, HTTPException):
            return error
        get_logger('mirofish.request').exception("Unhandled error on %s %s", request.method, request.path)
        return jsonify({"success": False, "error": "Internal server error"}), 500

    # 健康检查
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFish Backend'}
    
    if should_log_startup:
        logger.info("MiroFish Backend 启动完成")
    
    return app

