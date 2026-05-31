from __future__ import annotations

from pathlib import Path

from .baseline import make_baseline_strategy
from .config import AppSettings, load_settings
from .data import load_tasks
from .evaluator import HeuristicTutorEvaluator, LLMJudgeEvaluator
from .gates import GateChecker, GateThresholds
from .llm import HeuristicLLMClient, OpenAIResponsesClient
from .research_agent import LLMResearchAgent, SeededResearchAgent
from .runner import AutoresearchLoop, CandidateRunner
from .strategy import StrategyExecutor


def make_dry_run_loop(project_root: Path | None = None) -> AutoresearchLoop:
    settings = load_settings(project_root)
    llm = HeuristicLLMClient()
    executor = StrategyExecutor(llm=llm, settings=settings.model)
    runner = CandidateRunner(
        executor=executor,
        evaluator=HeuristicTutorEvaluator(),
        gate_checker=GateChecker(_thresholds_from_settings(settings)),
    )
    return AutoresearchLoop(
        runner=runner,
        research_agent=SeededResearchAgent(),
        baseline_strategy=make_baseline_strategy(),
        inner_loop_tasks=load_tasks(settings.project_root / "data/evals/smoke.jsonl"),
        checkpoint_tasks=load_tasks(settings.project_root / "data/evals/checkpoint.jsonl"),
        final_tasks=load_tasks(settings.project_root / "data/evals/final_private_template.jsonl"),
        thresholds=_thresholds_from_settings(settings),
    )


def make_openai_loop(
    *,
    project_root: Path | None = None,
    inner_loop_tasks_path: Path,
    checkpoint_tasks_path: Path,
    final_tasks_path: Path,
) -> AutoresearchLoop:
    settings = load_settings(project_root)
    llm = OpenAIResponsesClient(settings.model)
    executor = StrategyExecutor(llm=llm, settings=settings.model)
    runner = CandidateRunner(
        executor=executor,
        evaluator=LLMJudgeEvaluator(llm=llm, settings=settings.model),
        gate_checker=GateChecker(_thresholds_from_settings(settings)),
    )
    return AutoresearchLoop(
        runner=runner,
        research_agent=LLMResearchAgent(llm=llm, settings=settings.model),
        baseline_strategy=make_baseline_strategy(),
        inner_loop_tasks=load_tasks(inner_loop_tasks_path),
        checkpoint_tasks=load_tasks(checkpoint_tasks_path),
        final_tasks=load_tasks(final_tasks_path),
        thresholds=_thresholds_from_settings(settings),
    )


def _thresholds_from_settings(settings: AppSettings) -> GateThresholds:
    return GateThresholds(
        max_latency_seconds=settings.runtime.max_latency_per_candidate_seconds,
        max_cost_usd=settings.runtime.max_cost_per_candidate_usd,
    )
