from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from .baseline import make_baseline_strategy
from .benchmark_adapters import DEFAULT_SEED, prepare_benchmark_files
from .config import load_settings
from .data import load_tasks
from .factory import make_dry_run_loop, make_openai_loop
from .gates import GateResult
from .llm import OpenAIResponsesClient
from .modal_runner import evaluate_candidates_on_modal
from .research_agent import LLMResearchAgent
from .runner import select_frontier
from .schema import (
    CandidateEvaluation,
    CandidateStatus,
    EvalPhase,
    EvalTask,
    MetricScores,
    StrategySpec,
)
from .storage import RunStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Autoresearch tutor loop utilities.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check", help="Print local configuration without calling APIs.")

    prepare = subparsers.add_parser(
        "prepare-benchmarks",
        help="Build reproducible public and private eval JSONL files.",
    )
    prepare.add_argument("--seed", type=int, default=DEFAULT_SEED)

    dry_run = subparsers.add_parser(
        "dry-run", help="Run deterministic local pipeline verification only."
    )
    dry_run.add_argument("--output", type=Path, default=Path("runs/dry-run"))
    dry_run.add_argument("--initial-candidates", type=int, default=4)
    dry_run.add_argument("--followup-rounds", type=int, default=1)
    dry_run.add_argument("--followup-candidates", type=int, default=4)
    dry_run.add_argument("--checkpoint-count", type=int, default=2)

    run_local = subparsers.add_parser(
        "run-local-openai",
        help="Run the real OpenAI loop locally. Requires --confirm-run.",
    )
    run_local.add_argument("--inner-loop-tasks", type=Path, required=True)
    run_local.add_argument("--checkpoint-tasks", type=Path, required=True)
    run_local.add_argument("--final-tasks", type=Path, required=True)
    run_local.add_argument("--output", type=Path, default=Path("runs/openai-local"))
    run_local.add_argument("--initial-candidates", type=int, default=4)
    run_local.add_argument("--followup-rounds", type=int, default=1)
    run_local.add_argument("--followup-candidates", type=int, default=4)
    run_local.add_argument("--checkpoint-count", type=int, default=2)
    run_local.add_argument("--confirm-run", action="store_true")

    run_modal = subparsers.add_parser(
        "run-modal-openai",
        help="Run research locally and evaluate candidates on Modal. Requires --confirm-run.",
    )
    run_modal.add_argument("--inner-loop-tasks", type=Path, required=True)
    run_modal.add_argument("--checkpoint-tasks", type=Path, required=True)
    run_modal.add_argument("--final-tasks", type=Path, required=True)
    run_modal.add_argument("--output", type=Path, default=Path("runs/openai-modal"))
    run_modal.add_argument("--initial-candidates", type=int, default=4)
    run_modal.add_argument("--followup-rounds", type=int, default=1)
    run_modal.add_argument("--followup-candidates", type=int, default=4)
    run_modal.add_argument("--checkpoint-count", type=int, default=2)
    run_modal.add_argument("--max-wall-clock-minutes", type=float, default=180.0)
    run_modal.add_argument("--openai-budget-usd", type=float, default=270.0)
    run_modal.add_argument("--modal-budget-usd", type=float, default=270.0)
    run_modal.add_argument("--stop-budget-fraction", type=float, default=0.95)
    run_modal.add_argument("--confirm-run", action="store_true")

    resume_validation = subparsers.add_parser(
        "resume-modal-validation",
        help="Resume checkpoint/final validation from a persisted search history.",
    )
    resume_validation.add_argument("--history", type=Path, required=True)
    resume_validation.add_argument("--checkpoint-tasks", type=Path, required=True)
    resume_validation.add_argument("--final-tasks", type=Path, required=True)
    resume_validation.add_argument("--output", type=Path, required=True)
    resume_validation.add_argument("--checkpoint-count", type=int, default=4)
    resume_validation.add_argument("--openai-budget-usd", type=float, default=270.0)
    resume_validation.add_argument("--modal-budget-usd", type=float, default=270.0)
    resume_validation.add_argument("--stop-budget-fraction", type=float, default=0.95)
    resume_validation.add_argument("--max-wall-clock-minutes", type=float, default=180.0)
    resume_validation.add_argument("--confirm-run", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "check":
        return command_check()
    if args.command == "prepare-benchmarks":
        return command_prepare_benchmarks(args)
    if args.command == "dry-run":
        return command_dry_run(args)
    if args.command == "run-local-openai":
        return command_run_local_openai(args)
    if args.command == "run-modal-openai":
        return command_run_modal_openai(args)
    if args.command == "resume-modal-validation":
        return command_resume_modal_validation(args)
    raise AssertionError(f"Unhandled command: {args.command}")


def command_prepare_benchmarks(args: argparse.Namespace) -> int:
    build = prepare_benchmark_files(Path.cwd(), seed=args.seed)
    summary = {
        "inner_loop_tasks": str(build.inner_loop_path),
        "checkpoint_tasks": str(build.checkpoint_path),
        "private_final_tasks": str(build.private_final_path),
        "manifest": str(build.manifest_path),
        "counts": build.counts,
    }
    print(json.dumps(summary, indent=2))
    return 0


def command_check() -> int:
    settings = load_settings()
    print("Autoresearch tutor configuration")
    print(f"- tutor model: {settings.model.tutor_model} ({settings.model.tutor_reasoning_effort})")
    print(
        f"- research model: {settings.model.research_model} "
        f"({settings.model.research_reasoning_effort})"
    )
    print(f"- judge model: {settings.model.judge_model} ({settings.model.judge_reasoning_effort})")
    print(f"- text verbosity: {settings.model.text_verbosity}")
    print(f"- modal secret: {settings.runtime.modal_openai_secret_name}")
    print(f"- input cost estimate: ${os.getenv('OPENAI_INPUT_USD_PER_1M_TOKENS', '15.0')}/1M")
    print(f"- output cost estimate: ${os.getenv('OPENAI_OUTPUT_USD_PER_1M_TOKENS', '60.0')}/1M")
    print("- API calls: none")
    return 0


def command_dry_run(args: argparse.Namespace) -> int:
    loop = make_dry_run_loop()
    history = loop.dry_run(
        initial_candidates=args.initial_candidates,
        followup_rounds=args.followup_rounds,
        followup_candidates=args.followup_candidates,
        checkpoint_count=args.checkpoint_count,
    )
    store = RunStore(args.output)
    store.write_history(history)
    for evaluation in history:
        store.write_evaluation(evaluation)
        store.write_strategy(evaluation.strategy)
    frontier = select_frontier(history, limit=1)
    summary = {
        "candidate_count": len(history),
        "passed_count": sum(item.gate_result.passed for item in history),
        "rejected_count": sum(not item.gate_result.passed for item in history),
        "winner_candidate_id": frontier[0].candidate_id if frontier else None,
        "output": str(args.output),
    }
    store.write_summary(summary)
    print(json.dumps(summary, indent=2))
    return 0


def command_run_local_openai(args: argparse.Namespace) -> int:
    if not args.confirm_run:
        print("Refusing to run real OpenAI optimization without --confirm-run.")
        return 2
    loop = make_openai_loop(
        inner_loop_tasks_path=args.inner_loop_tasks,
        checkpoint_tasks_path=args.checkpoint_tasks,
        final_tasks_path=args.final_tasks,
    )
    history = loop.run_successive_halving(
        initial_candidates=args.initial_candidates,
        followup_rounds=args.followup_rounds,
        followup_candidates=args.followup_candidates,
        checkpoint_count=args.checkpoint_count,
        progress=True,
    )
    store = RunStore(args.output)
    store.write_history(history)
    for evaluation in history:
        store.write_evaluation(evaluation)
        store.write_strategy(evaluation.strategy)
    print(f"Wrote OpenAI local run artifacts to {args.output}")
    return 0


def command_run_modal_openai(args: argparse.Namespace) -> int:
    if not args.confirm_run:
        print("Refusing to run real Modal/OpenAI optimization without --confirm-run.")
        return 2

    settings = load_settings()
    llm = OpenAIResponsesClient(settings.model)
    research_agent = LLMResearchAgent(llm=llm, settings=settings.model)
    baseline_strategy = make_baseline_strategy()
    inner_tasks = load_tasks(args.inner_loop_tasks)
    checkpoint_tasks = load_tasks(args.checkpoint_tasks)
    final_tasks = load_tasks(args.final_tasks)
    store = RunStore(args.output)
    started_at = time.perf_counter()
    stop_reasons: list[str] = []

    history: list[CandidateEvaluation] = []
    print("[modal baseline] evaluating baseline", flush=True)
    baseline_eval = evaluate_candidates_on_modal(
        strategies=[baseline_strategy],
        tasks=inner_tasks,
        baseline_scores=MetricScores.neutral(),
        phase=EvalPhase.INNER_LOOP,
    )[0].model_copy(
        update={
            "status": CandidateStatus.PASSED,
            "gate_result": GateResult(passed=True),
            "rejection_reason": None,
        }
    )
    history.append(baseline_eval)
    persist_modal_progress(store=store, history=history)
    baseline_scores = baseline_eval.aggregate_scores

    if should_stop(args=args, history=history, started_at=started_at, stop_reasons=stop_reasons):
        return finish_modal_run(
            args=args,
            store=store,
            history=history,
            stop_reasons=stop_reasons,
            started_at=started_at,
        )

    print(f"[research] proposing {args.initial_candidates} initial candidates", flush=True)
    decisions = research_agent.propose(
        frontier=[baseline_eval],
        history=history,
        count=args.initial_candidates,
    )
    strategies = [decision.strategy for decision in decisions if decision.strategy is not None]
    print(f"[modal search] evaluating {len(strategies)} initial candidates", flush=True)
    history.extend(
        evaluate_candidates_on_modal(
            strategies=strategies,
            tasks=inner_tasks,
            baseline_scores=baseline_scores,
            phase=EvalPhase.INNER_LOOP,
        )
    )
    persist_modal_progress(store=store, history=history)
    no_pass_rounds = 0
    if not any(item.status == CandidateStatus.PASSED for item in history[1:]):
        no_pass_rounds += 1

    for round_idx in range(args.followup_rounds):
        if should_stop(args=args, history=history, started_at=started_at, stop_reasons=stop_reasons):
            break
        if no_pass_rounds >= 2:
            stop_reasons.append("no candidates passed hard gates in 2 consecutive search rounds")
            break
        frontier = select_frontier(history, limit=args.checkpoint_count)
        print(f"[research] round {round_idx + 1} frontier size {len(frontier)}", flush=True)
        decisions = research_agent.propose(
            frontier=frontier or [baseline_eval],
            history=history,
            count=args.followup_candidates,
        )
        strategies = [decision.strategy for decision in decisions if decision.strategy is not None]
        print(f"[modal search] evaluating {len(strategies)} follow-up candidates", flush=True)
        round_results = evaluate_candidates_on_modal(
            strategies=strategies,
            tasks=inner_tasks,
            baseline_scores=baseline_scores,
            phase=EvalPhase.INNER_LOOP,
        )
        history.extend(round_results)
        persist_modal_progress(store=store, history=history)
        if any(item.status == CandidateStatus.PASSED for item in round_results):
            no_pass_rounds = 0
        else:
            no_pass_rounds += 1

    if should_stop(args=args, history=history, started_at=started_at, stop_reasons=stop_reasons):
        return finish_modal_run(
            args=args,
            store=store,
            history=history,
            stop_reasons=stop_reasons,
            started_at=started_at,
        )

    top_strategies = [item.strategy for item in select_frontier(history, limit=args.checkpoint_count)]
    print(f"[modal checkpoint] evaluating baseline plus {len(top_strategies)} candidates", flush=True)
    checkpoint_baseline = evaluate_phase_baseline(
        baseline_strategy=baseline_strategy,
        tasks=checkpoint_tasks,
        phase=EvalPhase.CHECKPOINT,
    )
    checkpoint_results = [checkpoint_baseline]
    checkpoint_results.extend(
        evaluate_candidates_on_modal(
            strategies=top_strategies,
            tasks=checkpoint_tasks,
            baseline_scores=checkpoint_baseline.aggregate_scores,
            phase=EvalPhase.CHECKPOINT,
        )
    )
    history.extend(checkpoint_results)
    persist_modal_progress(store=store, history=history)

    if should_stop(args=args, history=history, started_at=started_at, stop_reasons=stop_reasons):
        return finish_modal_run(
            args=args,
            store=store,
            history=history,
            stop_reasons=stop_reasons,
            started_at=started_at,
        )

    final_frontier = select_frontier(checkpoint_results, limit=1)
    if final_frontier:
        print(f"[modal final] evaluating baseline and {final_frontier[0].candidate_id}", flush=True)
        final_baseline = evaluate_phase_baseline(
            baseline_strategy=baseline_strategy,
            tasks=final_tasks,
            phase=EvalPhase.FINAL,
        )
        final_candidate = evaluate_candidates_on_modal(
            strategies=[final_frontier[0].strategy],
            tasks=final_tasks,
            baseline_scores=final_baseline.aggregate_scores,
            phase=EvalPhase.FINAL,
        )
        history.extend([final_baseline, *final_candidate])
        persist_modal_progress(store=store, history=history)
    else:
        print("[modal final] no checkpoint candidate passed gates", flush=True)
        stop_reasons.append("no checkpoint candidate passed gates")

    return finish_modal_run(
        args=args,
        store=store,
        history=history,
        stop_reasons=stop_reasons,
        started_at=started_at,
    )


def command_resume_modal_validation(args: argparse.Namespace) -> int:
    if not args.confirm_run:
        print("Refusing to run real Modal/OpenAI validation without --confirm-run.")
        return 2

    started_at = time.perf_counter()
    baseline_strategy = make_baseline_strategy()
    checkpoint_tasks = load_tasks(args.checkpoint_tasks)
    final_tasks = load_tasks(args.final_tasks)
    history = [
        CandidateEvaluation.model_validate_json(line)
        for line in args.history.read_text().splitlines()
        if line.strip()
    ]
    history = [item for item in history if item.phase == EvalPhase.INNER_LOOP]
    store = RunStore(args.output)
    persist_modal_progress(store=store, history=history)

    top_strategies = [item.strategy for item in select_frontier(history, limit=args.checkpoint_count)]
    print(
        f"[resume checkpoint] evaluating baseline plus {len(top_strategies)} candidates",
        flush=True,
    )
    checkpoint_baseline = evaluate_phase_baseline(
        baseline_strategy=baseline_strategy,
        tasks=checkpoint_tasks,
        phase=EvalPhase.CHECKPOINT,
    )
    checkpoint_results = [checkpoint_baseline]
    checkpoint_results.extend(
        evaluate_candidates_on_modal(
            strategies=top_strategies,
            tasks=checkpoint_tasks,
            baseline_scores=checkpoint_baseline.aggregate_scores,
            phase=EvalPhase.CHECKPOINT,
        )
    )
    history.extend(checkpoint_results)
    persist_modal_progress(store=store, history=history)

    final_frontier = select_frontier(checkpoint_results, limit=1)
    stop_reasons: list[str] = []
    if final_frontier:
        print(f"[resume final] evaluating baseline and {final_frontier[0].candidate_id}", flush=True)
        final_baseline = evaluate_phase_baseline(
            baseline_strategy=baseline_strategy,
            tasks=final_tasks,
            phase=EvalPhase.FINAL,
        )
        final_results = evaluate_candidates_on_modal(
            strategies=[final_frontier[0].strategy],
            tasks=final_tasks,
            baseline_scores=final_baseline.aggregate_scores,
            phase=EvalPhase.FINAL,
        )
        history.extend([final_baseline, *final_results])
        persist_modal_progress(store=store, history=history)
    else:
        stop_reasons.append("no checkpoint candidate passed gates")

    return finish_modal_run(
        args=args,
        store=store,
        history=history,
        stop_reasons=stop_reasons,
        started_at=started_at,
    )


def finish_modal_run(
    *,
    args: argparse.Namespace,
    store: RunStore,
    history: list[CandidateEvaluation],
    stop_reasons: list[str],
    started_at: float,
) -> int:
    store.write_history(history)
    for evaluation in history:
        store.write_evaluation(evaluation)
        store.write_strategy(evaluation.strategy)
    winner = pick_winner(history)
    if winner is not None:
        winner_path = args.output / "winner_strategy.json"
        winner_path.write_text(winner.strategy.model_dump_json(indent=2))
    store.write_summary(
        build_run_summary(
            args=args,
            history=history,
            winner_candidate_id=winner.candidate_id if winner else None,
            stop_reasons=stop_reasons,
            elapsed_seconds=time.perf_counter() - started_at,
        )
    )
    print(f"Wrote Modal/OpenAI run artifacts to {args.output}")
    return 0


def evaluate_phase_baseline(
    *, baseline_strategy: StrategySpec, tasks: list[EvalTask], phase: EvalPhase
) -> CandidateEvaluation:
    return evaluate_candidates_on_modal(
        strategies=[baseline_strategy],
        tasks=tasks,
        baseline_scores=MetricScores.neutral(),
        phase=phase,
    )[0].model_copy(
        update={
            "status": CandidateStatus.PASSED,
            "gate_result": GateResult(passed=True),
            "rejection_reason": None,
        }
    )


def persist_modal_progress(*, store: RunStore, history: list[CandidateEvaluation]) -> None:
    store.write_history(history)
    for evaluation in history:
        store.write_evaluation(evaluation)
        store.write_strategy(evaluation.strategy)


def should_stop(
    *,
    args: argparse.Namespace,
    history: list[CandidateEvaluation],
    started_at: float,
    stop_reasons: list[str],
) -> bool:
    elapsed_minutes = (time.perf_counter() - started_at) / 60.0
    if elapsed_minutes >= args.max_wall_clock_minutes:
        stop_reasons.append("wall-clock optimization budget reached")
        return True

    summary = summarize_costs(history)
    if summary["estimated_openai_usd"] >= args.openai_budget_usd * args.stop_budget_fraction:
        stop_reasons.append("estimated OpenAI spend reached stop threshold")
        return True
    if summary["estimated_modal_usd"] >= args.modal_budget_usd * args.stop_budget_fraction:
        stop_reasons.append("estimated Modal spend reached stop threshold")
        return True
    return False


def pick_winner(history: list[CandidateEvaluation]) -> CandidateEvaluation | None:
    final_frontier = select_frontier(
        [item for item in history if item.phase == EvalPhase.FINAL],
        limit=1,
    )
    if final_frontier:
        return final_frontier[0]
    checkpoint_frontier = select_frontier(
        [item for item in history if item.phase == EvalPhase.CHECKPOINT],
        limit=1,
    )
    if checkpoint_frontier:
        return checkpoint_frontier[0]
    inner_frontier = select_frontier(history, limit=1)
    return inner_frontier[0] if inner_frontier else None


def build_run_summary(
    *,
    args: argparse.Namespace,
    history: list[CandidateEvaluation],
    winner_candidate_id: str | None,
    stop_reasons: list[str],
    elapsed_seconds: float,
) -> dict[str, object]:
    cost_summary = summarize_costs(history)
    return {
        "output": str(args.output),
        "elapsed_seconds": elapsed_seconds,
        "winner_candidate_id": winner_candidate_id,
        "stop_reasons": stop_reasons or ["completed configured optimization phases"],
        "candidate_count": len(history),
        "passed_count": sum(item.status == CandidateStatus.PASSED for item in history),
        "rejected_count": sum(item.status == CandidateStatus.REJECTED for item in history),
        "error_count": sum(item.status == CandidateStatus.ERROR for item in history),
        "phase_counts": count_by_phase(history),
        "costs": cost_summary,
        "budgets": {
            "openai_budget_usd": args.openai_budget_usd,
            "modal_budget_usd": args.modal_budget_usd,
            "stop_budget_fraction": args.stop_budget_fraction,
            "max_wall_clock_minutes": args.max_wall_clock_minutes,
        },
    }


def summarize_costs(history: list[CandidateEvaluation]) -> dict[str, float]:
    estimated_openai_usd = sum(float(item.cost_usd) for item in history)
    modal_worker_hour_rate = float(os.getenv("MODAL_ESTIMATED_USD_PER_WORKER_HOUR", "0.25"))
    estimated_modal_usd = (
        sum(float(item.latency_seconds) for item in history) / 3600.0 * modal_worker_hour_rate
    )
    return {
        "estimated_openai_usd": estimated_openai_usd,
        "estimated_modal_usd": estimated_modal_usd,
        "estimated_total_usd": estimated_openai_usd + estimated_modal_usd,
    }


def count_by_phase(history: list[CandidateEvaluation]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for evaluation in history:
        phase = str(evaluation.phase)
        counts[phase] = counts.get(phase, 0) + 1
    return counts
