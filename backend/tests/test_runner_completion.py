from types import SimpleNamespace

import pytest

from app.services import simulation_runner as sr
from app.services.simulation_runner import RunnerStatus, SimulationRunner


@pytest.fixture
def runner(monkeypatch):
    saved, synced, stopped = [], [], []
    state = SimpleNamespace(
        simulation_id="sim_t", runner_status=RunnerStatus.RUNNING, twitter_running=True,
        reddit_running=True, error=None, completed_at=None,
    )
    monkeypatch.setattr(SimulationRunner, "get_run_state", classmethod(lambda cls, sid: state))
    monkeypatch.setattr(SimulationRunner, "_save_run_state", classmethod(lambda cls, s: saved.append(s.runner_status)))
    monkeypatch.setattr(
        SimulationRunner, "_sync_simulation_status",
        classmethod(lambda cls, sid, status, error=None: synced.append(status)),
    )
    monkeypatch.setattr(sr.ZepGraphMemoryManager, "stop_updater", staticmethod(lambda sid: stopped.append(sid)))
    monkeypatch.setattr(SimulationRunner, "_graph_memory_enabled", {"sim_t": True})
    monkeypatch.setattr(SimulationRunner, "_completed_early", set())
    monkeypatch.setattr(SimulationRunner, "_manual_stop_requests", set())
    return SimpleNamespace(state=state, saved=saved, synced=synced, stopped=stopped)


def test_completion_is_published_through_the_ingestion_barrier(runner):
    SimulationRunner._publish_completion("sim_t", runner.state)
    assert runner.saved[0] == RunnerStatus.STOPPING  # barreira antes do estado final
    assert runner.state.runner_status == RunnerStatus.COMPLETED
    assert runner.state.completed_at and runner.stopped == ["sim_t"]
    assert "sim_t" in SimulationRunner._completed_early


def test_publish_is_idempotent_and_respects_manual_stop(runner):
    SimulationRunner._publish_completion("sim_t", runner.state)
    SimulationRunner._publish_completion("sim_t", runner.state)
    assert runner.stopped == ["sim_t"]

    runner.state.runner_status = RunnerStatus.RUNNING
    SimulationRunner._completed_early.clear()
    SimulationRunner._manual_stop_requests.add("sim_t")
    SimulationRunner._publish_completion("sim_t", runner.state)
    assert runner.state.runner_status == RunnerStatus.RUNNING


def test_failed_ingestion_drain_ends_as_failed(runner, monkeypatch):
    def boom(sid):
        raise RuntimeError("zep fora")

    monkeypatch.setattr(sr.ZepGraphMemoryManager, "stop_updater", staticmethod(boom))
    SimulationRunner._publish_completion("sim_t", runner.state)
    assert runner.state.runner_status == RunnerStatus.FAILED and runner.state.error
