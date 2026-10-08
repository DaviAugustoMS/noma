import pytest

from app import create_app
from app.services import report_insights as ri
from app.services.report_agent import Report, ReportManager, ReportStatus


class _LLM:
    def __init__(self, result):
        self.result = result
        self.messages = None

    def chat_json(self, messages, **_):
        self.messages = messages
        return self.result


def test_generate_cleans_limits_and_drops_garbage():
    llm = _LLM({
        "positives": [{"title": "  Boa   reação ", "detail": "Usuários gostaram."}, "só título", 42, {"detail": "sem título"}],
        "negatives": [{"title": f"R{i}", "detail": "x"} for i in range(20)],
        "improvements": "não é lista",
        "avoid": [], "new_points": [{"title": "Modo offline", "detail": "d" * 900}],
    })
    data = ri.generate_insights("# Relatório\n" + "texto " * 50, "Simular reação", llm=llm)
    assert data["positives"] == [{"title": "Boa reação", "detail": "Usuários gostaram."}, {"title": "só título", "detail": ""}]
    assert len(data["negatives"]) == 6 and data["improvements"] == []
    assert len(data["new_points"][0]["detail"]) == 500
    assert "untrusted" in llm.messages[0]["content"] and "LANGUAGE RULE" in llm.messages[1]["content"]


def test_generate_rejects_empty_report_and_empty_answer():
    with pytest.raises(ValueError):
        ri.generate_insights("   ", llm=_LLM({}))
    with pytest.raises(ValueError):
        ri.generate_insights("texto", llm=_LLM({"positives": []}))


def test_merge_replaces_previous_section_instead_of_duplicating():
    first = {"positives": [{"title": "A", "detail": "a"}], **{k: [] for k in ri.CATEGORIES if k != "positives"}}
    second = {"negatives": [{"title": "B", "detail": ""}], **{k: [] for k in ri.CATEGORIES if k != "negatives"}}
    once = ri.merge_into_markdown("# R\n\ncorpo", first)
    twice = ri.merge_into_markdown(once, second)
    assert twice.count(ri.MARK_START) == 1 and "**B**" in twice and "**A**" not in twice
    assert twice.startswith("# R\n\ncorpo") and ri.strip_from_markdown(twice).strip() == "# R\n\ncorpo"


def test_save_and_load_roundtrip(tmp_path):
    data = {k: [] for k in ri.CATEGORIES}
    data["avoid"] = [{"title": "Jargão", "detail": "Afasta o RH."}]
    ri.save(str(tmp_path), data)
    assert ri.load(str(tmp_path))["avoid"][0]["title"] == "Jargão"
    assert ri.load(str(tmp_path / "nao-existe")) is None


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(ReportManager, "REPORTS_DIR", str(tmp_path))
    app = create_app()
    app.config["API_AUTH_REQUIRED"] = False
    report = Report(
        report_id="report_t1", simulation_id="sim_t1", graph_id="g", simulation_requirement="req",
        status=ReportStatus.COMPLETED, markdown_content="# R\n\n" + "conteudo " * 30,
    )
    ReportManager.save_report(report)
    return app.test_client()


def test_routes_generate_then_read_and_attach_to_download(client, monkeypatch):
    fake = {k: [] for k in ri.CATEGORIES}
    fake["positives"] = [{"title": "Confiança", "detail": "Local primeiro."}]
    monkeypatch.setattr(ri, "generate_insights", lambda md, req="", llm=None: fake)

    assert client.get("/api/report/report_t1/insights").get_json()["data"] is None
    assert client.post("/api/report/report_t1/insights").get_json()["data"]["positives"][0]["title"] == "Confiança"
    assert client.get("/api/report/report_t1/insights").get_json()["data"]["positives"][0]["title"] == "Confiança"
    assert "**Confiança**" in client.get("/api/report/report_t1/download").get_data(as_text=True)
    assert client.get("/api/report/report_t1/insights").status_code == 200


def test_routes_errors(client, monkeypatch):
    assert client.get("/api/report/report_x9/insights").status_code == 404
    assert client.post("/api/report/report_x9/insights").status_code == 404

    def boom(*a, **k):
        raise RuntimeError("llm fora")

    monkeypatch.setattr(ri, "generate_insights", boom)
    response = client.post("/api/report/report_t1/insights")
    assert response.status_code == 502 and response.get_json()["code"] == "insightsFailed"
