from pathlib import Path

from autoresearch_tutor.factory import make_dry_run_loop
from autoresearch_tutor.runner import select_frontier
from autoresearch_tutor.schema import EvalPhase


def test_dry_run_loop_reaches_final_phase() -> None:
    loop = make_dry_run_loop(Path.cwd())

    history = loop.run_successive_halving(
        initial_candidates=4,
        followup_rounds=1,
        followup_candidates=4,
        checkpoint_count=2,
    )

    assert history
    assert any(item.phase == EvalPhase.CHECKPOINT for item in history)
    assert any(item.phase == EvalPhase.FINAL for item in history)
    assert select_frontier(history, limit=1)
