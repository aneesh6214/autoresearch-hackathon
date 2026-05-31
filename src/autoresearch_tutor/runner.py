from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

from .constraints import strategy_constraint_failures
from .evaluator import TutorEvaluator
from .gates import GateChecker, GateThresholds
from .research_agent import ResearchAgent
from .schema import (
    CandidateEvaluation,
    CandidateStatus,
    EvalPhase,
    EvalTask,
    GateResult,
    JudgeOutput,
    MetricScores,
    StrategySpec,
    TutorTranscript,
    new_id,
    now_utc,
)
from .strategy import StrategyExecutor


@dataclass(frozen=True)
class EvaluationContext:
    phase: EvalPhase
    baseline_scores: MetricScores
    thresholds: GateThresholds


class CandidateRunner:
    def __init__(
        self,
        *,
        executor: StrategyExecutor,
        evaluator: TutorEvaluator,
        gate_checker: GateChecker,
    ) -> None:
        self.executor = executor
        self.evaluator = evaluator
        self.gate_checker = gate_checker

    def evaluate(
        self,
        *,
        strategy: StrategySpec,
        tasks: list[EvalTask],
        context: EvaluationContext,
        progress: bool = False,
    ) -> CandidateEvaluation:
        constraint_failures = strategy_constraint_failures(strategy)
        if constraint_failures:
            return CandidateEvaluation(
                candidate_id=strategy.candidate_id,
                phase=context.phase,
                status=CandidateStatus.REJECTED,
                strategy=strategy,
                aggregate_scores=MetricScores.neutral(),
                gate_result=GateResult(passed=False, failures=constraint_failures),
                benchmark_subset_ids=[task.task_id for task in tasks],
                rejection_reason="; ".join(constraint_failures),
            )

        transcripts: list[TutorTranscript] = []
        judge_outputs: list[JudgeOutput] = []
        try:
            for idx, task in enumerate(tasks, start=1):
                if progress:
                    print(
                        f"[{context.phase}] {strategy.candidate_id}: "
                        f"task {idx}/{len(tasks)} {task.task_id}",
                        flush=True,
                    )
                transcript = self.executor.run(strategy, task)
                transcripts.append(transcript)
                judge_outputs.append(self.evaluator.evaluate(task, transcript))
        except Exception as exc:
            return CandidateEvaluation(
                candidate_id=strategy.candidate_id,
                phase=context.phase,
                status=CandidateStatus.ERROR,
                strategy=strategy,
                aggregate_scores=MetricScores.neutral(),
                gate_result=GateResult(passed=False, failures=[f"evaluation error: {exc}"]),
                transcripts=transcripts,
                judge_outputs=judge_outputs,
                benchmark_subset_ids=[task.task_id for task in tasks],
                rejection_reason=str(exc),
            )

        aggregate = MetricScores.mean([judge.scores for judge in judge_outputs])
        latency = sum(transcript.latency_seconds for transcript in transcripts)
        cost = estimate_cost_usd(transcripts, judge_outputs)
        average_task_latency = latency / max(len(tasks), 1)
        gate = self.gate_checker.check(
            candidate=aggregate,
            baseline=context.baseline_scores,
            latency_seconds=average_task_latency,
            cost_usd=cost,
        )
        status = CandidateStatus.PASSED if gate.passed else CandidateStatus.REJECTED
        rejection = None if gate.passed else "; ".join(gate.failures)
        return CandidateEvaluation(
            candidate_id=strategy.candidate_id,
            phase=context.phase,
            status=status,
            strategy=strategy,
            aggregate_scores=aggregate,
            gate_result=gate,
            transcripts=transcripts,
            judge_outputs=judge_outputs,
            benchmark_subset_ids=[task.task_id for task in tasks],
            rejection_reason=rejection,
            cost_usd=cost,
            latency_seconds=latency,
        )


class AutoresearchLoop:
    def __init__(
        self,
        *,
        runner: CandidateRunner,
        research_agent: ResearchAgent,
        baseline_strategy: StrategySpec,
        inner_loop_tasks: list[EvalTask],
        checkpoint_tasks: list[EvalTask],
        final_tasks: list[EvalTask],
        thresholds: GateThresholds | None = None,
    ) -> None:
        self.runner = runner
        self.research_agent = research_agent
        self.baseline_strategy = baseline_strategy
        self.inner_loop_tasks = inner_loop_tasks
        self.checkpoint_tasks = checkpoint_tasks
        self.final_tasks = final_tasks
        self.thresholds = thresholds or GateThresholds()

    def run_successive_halving(
        self,
        *,
        initial_candidates: int = 4,
        followup_rounds: int = 1,
        followup_candidates: int = 4,
        checkpoint_count: int = 2,
        progress: bool = False,
    ) -> list[CandidateEvaluation]:
        """Run budget-aware successive halving with the configured components."""

        history: list[CandidateEvaluation] = []
        if progress:
            print("[baseline] evaluating baseline", flush=True)
        baseline_eval = self._evaluate_baseline(
            self.inner_loop_tasks, EvalPhase.INNER_LOOP, progress=progress
        )
        history.append(baseline_eval)
        baseline_scores = baseline_eval.aggregate_scores
        context = EvaluationContext(
            phase=EvalPhase.INNER_LOOP,
            baseline_scores=baseline_scores,
            thresholds=self.thresholds,
        )

        decisions = self.research_agent.propose(
            frontier=[baseline_eval],
            history=history,
            count=initial_candidates,
        )
        if progress:
            print(f"[search] evaluating {len(decisions)} initial candidates", flush=True)
        history.extend(
            self._evaluate_decisions(decisions, self.inner_loop_tasks, context, progress=progress)
        )

        for _ in range(followup_rounds):
            frontier = select_frontier(history, limit=checkpoint_count)
            if progress:
                print(f"[search] frontier size: {len(frontier)}", flush=True)
            decisions = self.research_agent.propose(
                frontier=frontier,
                history=history,
                count=followup_candidates,
            )
            if progress:
                print(f"[search] evaluating {len(decisions)} follow-up candidates", flush=True)
            history.extend(
                self._evaluate_decisions(decisions, self.inner_loop_tasks, context, progress=progress)
            )

        checkpoint_context = EvaluationContext(
            phase=EvalPhase.CHECKPOINT,
            baseline_scores=baseline_scores,
            thresholds=self.thresholds,
        )
        top_strategies = [item.strategy for item in select_frontier(history, limit=checkpoint_count)]
        if progress:
            print(f"[checkpoint] evaluating {len(top_strategies)} candidates", flush=True)
        for strategy in top_strategies:
            history.append(
                self.runner.evaluate(
                    strategy=strategy,
                    tasks=self.checkpoint_tasks,
                    context=checkpoint_context,
                    progress=progress,
                )
            )

        final_frontier = select_frontier(
            [item for item in history if item.phase == EvalPhase.CHECKPOINT],
            limit=1,
        )
        if final_frontier:
            if progress:
                print(f"[final] evaluating {final_frontier[0].candidate_id}", flush=True)
            final_context = EvaluationContext(
                phase=EvalPhase.FINAL,
                baseline_scores=baseline_scores,
                thresholds=self.thresholds,
            )
            history.append(
                self.runner.evaluate(
                    strategy=final_frontier[0].strategy,
                    tasks=self.final_tasks,
                    context=final_context,
                    progress=progress,
                )
            )
        return history

    def dry_run(
        self,
        *,
        initial_candidates: int = 4,
        followup_rounds: int = 1,
        followup_candidates: int = 4,
        checkpoint_count: int = 2,
    ) -> list[CandidateEvaluation]:
        """Backward-compatible alias for deterministic local verification."""

        return self.run_successive_halving(
            initial_candidates=initial_candidates,
            followup_rounds=followup_rounds,
            followup_candidates=followup_candidates,
            checkpoint_count=checkpoint_count,
        )

    def _evaluate_baseline(
        self, tasks: list[EvalTask], phase: EvalPhase, progress: bool = False
    ) -> CandidateEvaluation:
        neutral_context = EvaluationContext(
            phase=phase,
            baseline_scores=MetricScores.neutral(),
            thresholds=self.thresholds,
        )
        evaluation = self.runner.evaluate(
            strategy=self.baseline_strategy,
            tasks=tasks,
            context=neutral_context,
            progress=progress,
        )
        # The baseline defines the yardstick, so it should not reject itself.
        return evaluation.model_copy(
            update={
                "status": CandidateStatus.PASSED,
                "gate_result": GateResult(passed=True),
                "rejection_reason": None,
            }
        )

    def _evaluate_decisions(
        self,
        decisions: Iterable,
        tasks: list[EvalTask],
        context: EvaluationContext,
        progress: bool = False,
    ) -> list[CandidateEvaluation]:
        evaluations: list[CandidateEvaluation] = []
        for decision in decisions:
            if decision.strategy is None:
                continue
            evaluations.append(
                self.runner.evaluate(
                    strategy=decision.strategy,
                    tasks=tasks,
                    context=context,
                    progress=progress,
                )
            )
        return evaluations


def select_frontier(
    evaluations: list[CandidateEvaluation], *, limit: int
) -> list[CandidateEvaluation]:
    valid = [
        item
        for item in evaluations
        if item.status == CandidateStatus.PASSED
        and item.strategy.generation_action.value != "baseline"
    ]
    valid.sort(
        key=lambda item: (
            item.aggregate_scores.display_score,
            item.aggregate_scores.core_quality_score,
            -item.aggregate_scores.answer_leakage,
            -item.cost_usd,
        ),
        reverse=True,
    )
    return valid[:limit]


def estimate_cost_usd(
    transcripts: list[TutorTranscript], judge_outputs: list[JudgeOutput] | None = None
) -> float:
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    for usage in [
        *(transcript.token_usage for transcript in transcripts),
        *(judge.token_usage for judge in judge_outputs or []),
    ]:
        input_tokens += usage.get("input_tokens", 0)
        output_tokens += usage.get("output_tokens", 0)
        total_tokens += usage.get("total_tokens", 0)

    unclassified_tokens = max(0, total_tokens - input_tokens - output_tokens)
    input_cost_per_million = float(os.getenv("OPENAI_INPUT_USD_PER_1M_TOKENS", "15.0"))
    output_cost_per_million = float(os.getenv("OPENAI_OUTPUT_USD_PER_1M_TOKENS", "60.0"))
    unclassified_cost_per_million = float(os.getenv("OPENAI_TOTAL_USD_PER_1M_TOKENS", "30.0"))
    return (
        input_tokens * input_cost_per_million
        + output_tokens * output_cost_per_million
        + unclassified_tokens * unclassified_cost_per_million
    ) / 1_000_000.0


def make_run_id() -> str:
    timestamp = now_utc().strftime("%Y%m%dT%H%M%SZ")
    return f"run_{timestamp}_{new_id('id')}"
