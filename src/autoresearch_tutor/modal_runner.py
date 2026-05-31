from __future__ import annotations

import json

from .modal_app import app, evaluate_candidate_remote
from .schema import CandidateEvaluation, EvalPhase, EvalTask, MetricScores, StrategySpec


def evaluate_candidates_on_modal(
    *,
    strategies: list[StrategySpec],
    tasks: list[EvalTask],
    baseline_scores: MetricScores,
    phase: EvalPhase,
) -> list[CandidateEvaluation]:
    """Evaluate candidates with Modal workers.

    This function submits remote work only when explicitly called. It is kept
    separate from the local CLI so imports and tests do not launch Modal jobs.
    """

    if not strategies:
        return []

    tasks_json = json.dumps([task.model_dump() for task in tasks], default=str)
    baseline_scores_json = baseline_scores.model_dump_json()
    payloads = [
        {
            "strategy_json": strategy.model_dump_json(),
            "tasks_json": tasks_json,
            "baseline_scores_json": baseline_scores_json,
            "phase": phase.value,
        }
        for strategy in strategies
    ]
    with app.run():
        results = list(evaluate_candidate_remote.map(payloads))
    return [CandidateEvaluation.model_validate_json(result) for result in results]
