import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import sim_common  # noqa: E402


def _config(active_hours, start_hour=None):
    time_config = {} if start_hour is None else {"start_hour": start_hour}
    return {
        "time_config": time_config,
        "agent_configs": [{"agent_id": i, "active_hours": h} for i, h in enumerate(active_hours)],
    }


def test_full_runs_keep_legacy_midnight_start():
    assert sim_common.resolve_start_hour(_config([[9, 10], [18, 19]]), None) == 0


def test_short_runs_start_at_first_active_hour():
    cfg = _config([[9, 10, 11], [8, 9, 10], [18, 19, 20]])
    assert sim_common.resolve_start_hour(cfg, 2) == 8


def test_configured_start_hour_wins():
    assert sim_common.resolve_start_hour(_config([[9]], start_hour=14), 2) == 14
    assert sim_common.resolve_start_hour(_config([[9]], start_hour=14), None) == 14


def test_short_run_without_active_hours_falls_back_to_zero():
    assert sim_common.resolve_start_hour({"agent_configs": [{"agent_id": 0}]}, 2) == 0


def _make_db(path, actions):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE trace (user_id INTEGER, action TEXT, info TEXT, created_at TEXT)")
    for user_id, action, info in actions:
        conn.execute("INSERT INTO trace VALUES (?, ?, ?, '0')", (user_id, action, json.dumps(info)))
    conn.commit()
    conn.close()


def test_max_rowid_and_incremental_fetch_skip_initial_rows(tmp_path):
    db = str(tmp_path / "sim.db")
    assert sim_common.get_max_rowid(db) == 0

    _make_db(db, [(0, "sign_up", {}), (0, "create_post", {"content": "inicial"})])
    baseline = sim_common.get_max_rowid(db)
    assert baseline == 2

    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO trace VALUES (1, 'create_post', ?, '1')", (json.dumps({"content": "novo"}),))
    conn.execute("INSERT INTO trace VALUES (1, 'refresh', '{}', '1')")
    conn.commit()
    conn.close()

    actions, last = sim_common.fetch_new_actions_from_db(db, baseline, {1: "Maria"})
    assert last == baseline + 2
    assert [a["action_type"] for a in actions] == ["CREATE_POST"]  # 'refresh' é filtrado
    assert actions[0]["agent_name"] == "Maria"
    assert actions[0]["action_args"]["content"] == "novo"
