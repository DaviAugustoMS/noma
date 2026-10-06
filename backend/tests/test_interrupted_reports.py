import json

import pytest

from app.services.report_agent import ReportManager


@pytest.fixture()
def reports_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ReportManager, "REPORTS_DIR", str(tmp_path))
    return tmp_path


def _write(reports_dir, report_id, meta_status=None, progress_status=None, sections=("S1",)):
    folder = reports_dir / report_id
    folder.mkdir()
    if meta_status:
        (folder / "meta.json").write_text(
            json.dumps({"report_id": report_id, "status": meta_status, "error": None}), encoding="utf-8")
    if progress_status:
        (folder / "progress.json").write_text(
            json.dumps({"status": progress_status, "progress": 66, "message": "Gerando",
                        "completed_sections": list(sections)}), encoding="utf-8")


def _read(reports_dir, report_id, name):
    return json.loads((reports_dir / report_id / name).read_text(encoding="utf-8"))


def test_orphaned_reports_are_marked_failed_and_keep_progress_data(reports_dir):
    _write(reports_dir, "r_stuck", meta_status="planning", progress_status="generating", sections=("A", "B"))

    assert ReportManager.mark_interrupted_reports() == ["r_stuck"]

    meta = _read(reports_dir, "r_stuck", "meta.json")
    progress = _read(reports_dir, "r_stuck", "progress.json")
    assert meta["status"] == "failed" and "interrupted" in meta["error"]
    assert progress["status"] == "failed"
    assert progress["completed_sections"] == ["A", "B"]  # seções escritas são preservadas
    assert progress["progress"] == 66


def test_finished_reports_are_left_untouched(reports_dir):
    _write(reports_dir, "r_done", meta_status="completed", progress_status="completed")
    _write(reports_dir, "r_failed", meta_status="failed", progress_status="failed")
    # meta atrasado, mas o progresso já diz concluído: vale o progresso
    _write(reports_dir, "r_race", meta_status="generating", progress_status="completed")

    assert ReportManager.mark_interrupted_reports() == []
    assert _read(reports_dir, "r_done", "meta.json")["status"] == "completed"
    assert _read(reports_dir, "r_race", "meta.json")["status"] == "generating"


def test_meta_only_and_missing_dir_are_handled(reports_dir, monkeypatch):
    _write(reports_dir, "r_meta_only", meta_status="pending")
    (reports_dir / "r_empty").mkdir()
    assert ReportManager.mark_interrupted_reports() == ["r_meta_only"]

    monkeypatch.setattr(ReportManager, "REPORTS_DIR", str(reports_dir / "nao_existe"))
    assert ReportManager.mark_interrupted_reports() == []
