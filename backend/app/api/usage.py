"""Gasto de tokens do LLM: leitura por projeto e total geral, e escopo por requisição."""

from __future__ import annotations

from flask import jsonify, request

from . import usage_bp
from ..models.project import ProjectManager
from ..services.simulation_manager import SimulationManager
from ..utils import usage
from ..utils.logger import get_logger

logger = get_logger('mirofish.usage')

# Rotas que chamam o LLM no processo do backend -> etapa do gasto.
_ENDPOINT_STAGE = {
    'graph.retry_ontology': 'ontology',
    'simulation.prepare_simulation': 'prepare',
    'simulation.generate_profiles': 'prepare',
    'simulation.interview_agent': 'interviews',
    'simulation.interview_agents_batch': 'interviews',
    'simulation.interview_all_agents': 'interviews',
    'report.generate_report': 'report',
    'report.chat_with_report_agent': 'chat',
    'report.search_graph_tool': 'report',
    'report.get_graph_statistics_tool': 'report',
}


def _project_of_simulation(simulation_id: str | None) -> str | None:
    if not simulation_id:
        return None
    state = SimulationManager().get_simulation(str(simulation_id))
    return state.project_id if state else None


def _project_of_report(report_id: str | None) -> str | None:
    if not report_id:
        return None
    from ..services.report_agent import ReportManager

    report = ReportManager.get_report(str(report_id))
    return _project_of_simulation(report.simulation_id) if report else None


def resolve_project(project_id=None, simulation_id=None, report_id=None) -> str | None:
    if project_id:
        return str(project_id)
    return _project_of_simulation(simulation_id) or _project_of_report(report_id)


def bind_request_scope():
    """before_request: define o escopo de uso (projeto + etapa) das rotas que chamam o LLM."""

    stage = _ENDPOINT_STAGE.get(request.endpoint or '')
    if not stage:
        return None
    try:
        body = request.get_json(silent=True)
        body = body if isinstance(body, dict) else {}
        project_id = resolve_project(
            body.get('project_id') or request.args.get('project_id'),
            body.get('simulation_id') or request.args.get('simulation_id'),
            body.get('report_id') or request.args.get('report_id'),
        )
        usage.bind(project_id, stage)
    except Exception:  # noqa: BLE001 - contar nunca pode derrubar a requisição
        logger.warning("Não foi possível definir o escopo de uso da requisição", exc_info=True)
    return None


@usage_bp.route('', methods=['GET'])
def get_usage():
    """Gasto de um projeto: ?project_id= | ?simulation_id= | ?report_id= (sem filtro = total geral)."""

    args = request.args
    if not any(args.get(k) for k in ('project_id', 'simulation_id', 'report_id')):
        return jsonify({"success": True, "data": {"scope": "all", **usage.all_usage()}})
    project_id = resolve_project(args.get('project_id'), args.get('simulation_id'), args.get('report_id'))
    if not project_id or (args.get('project_id') and not ProjectManager.get_project(project_id)):
        return jsonify({"success": True, "data": {"scope": "project", **usage.project_usage(usage.SEM_PROJETO)}})
    return jsonify({"success": True, "data": {"scope": "project", "project_id": project_id, **usage.project_usage(project_id)}})
