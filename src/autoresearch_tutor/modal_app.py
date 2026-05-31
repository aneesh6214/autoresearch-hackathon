from __future__ import annotations

import json
import os

import modal

from .config import load_settings
from .evaluator import LLMJudgeEvaluator
from .gates import GateChecker, GateThresholds
from .llm import OpenAIResponsesClient
from .runner import CandidateRunner, EvaluationContext
from .schema import EvalPhase, EvalTask, MetricScores, StrategySpec
from .strategy import StrategyExecutor


SECRET_NAME = os.getenv("MODAL_OPENAI_SECRET_NAME", "openai-api-key")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_pyproject("pyproject.toml")
    .add_local_python_source("autoresearch_tutor")
)

app = modal.App("autoresearch-tutor")


@app.function(
    image=image,
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    timeout=900,
)
def evaluate_candidate_remote(
    payload: dict[str, str],
) -> str:
    settings = load_settings()
    llm = OpenAIResponsesClient(settings.model)
    runner = CandidateRunner(
        executor=StrategyExecutor(llm=llm, settings=settings.model),
        evaluator=LLMJudgeEvaluator(llm=llm, settings=settings.model),
        gate_checker=GateChecker(
            GateThresholds(
                max_latency_seconds=settings.runtime.max_latency_per_candidate_seconds,
                max_cost_usd=settings.runtime.max_cost_per_candidate_usd,
            )
        ),
    )
    strategy = StrategySpec.model_validate_json(payload["strategy_json"])
    tasks = [EvalTask.model_validate(item) for item in json.loads(payload["tasks_json"])]
    baseline_scores = MetricScores.model_validate_json(payload["baseline_scores_json"])
    evaluation = runner.evaluate(
        strategy=strategy,
        tasks=tasks,
        context=EvaluationContext(
            phase=EvalPhase(payload["phase"]),
            baseline_scores=baseline_scores,
            thresholds=GateThresholds(),
        ),
    )
    return evaluation.model_dump_json()


@app.local_entrypoint()
def info() -> None:
    print("Modal app is defined. No optimization loop is started by this entrypoint.")
    print("Remote function: evaluate_candidate_remote")
