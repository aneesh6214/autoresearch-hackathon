from __future__ import annotations

import json
from collections import Counter

from pydantic import ValidationError

from .config import ModelSettings
from .llm import LLMClient
from .schema import (
    CandidateEvaluation,
    GenerationAction,
    ResearchDecision,
    ResponseArchitecture,
    StrategySpec,
    new_id,
)


RESEARCH_SYSTEM = """You are a research agent optimizing AI tutoring strategies.

You may propose bounded tutor strategy programs using these primitives:
- response architecture: single_pass, plan_then_answer, self_critique_revise, diagnose_then_tutor
- tutor policy prompt
- optional hidden planning prompt
- optional self-critique prompt
- 0-3 synthetic few-shot tutoring examples
- output structure

You cannot edit benchmarks, judges, gates, model choices, decoding parameters,
hidden evals, or scoring weights. Do not hardcode benchmark answers or optimize
for evaluator approval language. Optimize real tutoring behavior."""


class ResearchAgent:
    def propose(
        self,
        *,
        frontier: list[CandidateEvaluation],
        history: list[CandidateEvaluation],
        count: int,
    ) -> list[ResearchDecision]:
        raise NotImplementedError


class LLMResearchAgent(ResearchAgent):
    def __init__(self, llm: LLMClient, settings: ModelSettings) -> None:
        self.llm = llm
        self.settings = settings

    def propose(
        self,
        *,
        frontier: list[CandidateEvaluation],
        history: list[CandidateEvaluation],
        count: int,
    ) -> list[ResearchDecision]:
        data = self.llm.complete_json(
            model=self.settings.research_model,
            system=RESEARCH_SYSTEM,
            user=render_research_prompt(frontier=frontier, history=history, count=count),
            reasoning_effort=self.settings.research_reasoning_effort,
            text_verbosity=self.settings.text_verbosity,
            max_output_tokens=self.settings.max_output_tokens,
        )
        candidates = data.get("candidates", [])
        if not isinstance(candidates, list):
            raise ValueError("Research agent output must contain a candidates list")
        decisions: list[ResearchDecision] = []
        for raw in candidates[:count]:
            try:
                decisions.append(parse_research_candidate(raw))
            except ValueError:
                continue
        if not decisions:
            return SeededResearchAgent().propose(frontier=frontier, history=history, count=count)
        return decisions


class SeededResearchAgent(ResearchAgent):
    """Deterministic candidate proposer for dry runs and tests."""

    def __init__(self) -> None:
        self.round = 0

    def propose(
        self,
        *,
        frontier: list[CandidateEvaluation],
        history: list[CandidateEvaluation],
        count: int,
    ) -> list[ResearchDecision]:
        self.round += 1
        parent_ids = [item.candidate_id for item in frontier[:2]]
        options = [
            (
                ResponseArchitecture.SINGLE_PASS,
                "Lead with a concise misconception diagnosis, then give one targeted hint.",
                "diagnosis-forward concise policy",
            ),
            (
                ResponseArchitecture.PLAN_THEN_ANSWER,
                "Privately diagnose the misconception and answer-leakage risk before giving a hint.",
                "hidden planning policy",
            ),
            (
                ResponseArchitecture.SELF_CRITIQUE_REVISE,
                "Draft a response, check it for answer leakage and vague questioning, then revise.",
                "self-critique policy",
            ),
            (
                ResponseArchitecture.DIAGNOSE_THEN_TUTOR,
                "Classify student state, locate the error, and give one micro-step plus handoff.",
                "diagnosis-then-tutor policy",
            ),
        ]
        decisions: list[ResearchDecision] = []
        for idx in range(count):
            architecture, policy, label = options[idx % len(options)]
            action = GenerationAction.SEED if not history else GenerationAction.MUTATION
            strategy = StrategySpec(
                candidate_id=new_id("cand"),
                parent_candidate_ids=parent_ids,
                generation_action=action,
                response_architecture=architecture,
                tutor_policy=f"{policy} Variant {idx + 1}: prioritize the current worst failure mode.",
                output_structure=(
                    "Student-facing response: brief diagnosis if useful, one hint or "
                    "micro-step, and one concrete next question."
                ),
                rationale=f"Dry-run {label}; round {self.round}.",
            )
            decisions.append(
                ResearchDecision(
                    action=action,
                    rationale=f"Try {label} against current failure modes.",
                    parent_candidate_ids=parent_ids,
                    strategy=strategy,
                )
            )
        return decisions


def render_research_prompt(
    *, frontier: list[CandidateEvaluation], history: list[CandidateEvaluation], count: int
) -> str:
    return f"""Propose {count} next tutor strategy candidates.

Current frontier:
{json.dumps([summarize_evaluation(item) for item in frontier], indent=2)}

Recent history:
{json.dumps([summarize_evaluation(item) for item in history[-12:]], indent=2)}

Dominant failure modes:
{json.dumps(summarize_failure_modes(history), indent=2)}

Return JSON:
{{
  "candidates": [
    {{
      "action": "seed|mutation|recombination|repair|ablation",
      "rationale": "why this is the next useful experiment",
      "target_failure_mode": "short label or null",
      "parent_candidate_ids": ["candidate id"],
      "strategy": {{
        "response_architecture": "single_pass|plan_then_answer|self_critique_revise|diagnose_then_tutor",
        "tutor_policy": "policy text",
        "output_structure": "student-facing structure",
        "hidden_planning_prompt": "optional prompt or null",
        "self_critique_prompt": "optional prompt or null",
        "few_shot_examples": [
          {{"student": "synthetic student message", "tutor": "ideal tutor response", "notes": "why"}}
        ]
      }}
    }}
  ]
}}"""


def parse_research_candidate(raw: dict) -> ResearchDecision:
    strategy_data = dict(raw.get("strategy") or {})
    strategy_data.setdefault("candidate_id", new_id("cand"))
    action = normalize_generation_action(raw.get("action"), strategy_data)
    strategy_data["generation_action"] = action
    strategy_data["parent_candidate_ids"] = raw.get("parent_candidate_ids", [])
    strategy_data["rationale"] = raw.get("rationale", "")
    try:
        strategy = StrategySpec(**strategy_data)
    except ValidationError as exc:
        raise ValueError(f"Invalid research candidate: {exc}") from exc
    return ResearchDecision(
        action=strategy.generation_action,
        rationale=str(raw.get("rationale", "")),
        target_failure_mode=raw.get("target_failure_mode"),
        parent_candidate_ids=strategy.parent_candidate_ids,
        strategy=strategy,
    )


def normalize_generation_action(
    raw_action: object, strategy_data: dict[str, object]
) -> GenerationAction:
    action_value = str(raw_action or GenerationAction.MUTATION.value)
    valid_actions = {item.value for item in GenerationAction}
    if action_value in valid_actions:
        return GenerationAction(action_value)

    valid_architectures = {item.value for item in ResponseArchitecture}
    if action_value in valid_architectures and "response_architecture" not in strategy_data:
        strategy_data["response_architecture"] = action_value
    return GenerationAction.MUTATION


def summarize_evaluation(evaluation: CandidateEvaluation) -> dict:
    return {
        "candidate_id": evaluation.candidate_id,
        "status": evaluation.status,
        "architecture": evaluation.strategy.response_architecture,
        "action": evaluation.strategy.generation_action,
        "display_score": round(evaluation.aggregate_scores.display_score, 4),
        "core_quality_score": round(evaluation.aggregate_scores.core_quality_score, 4),
        "answer_leakage": round(evaluation.aggregate_scores.answer_leakage, 4),
        "harm_rate": round(evaluation.aggregate_scores.harm_rate, 4),
        "cost_usd": round(evaluation.cost_usd, 4),
        "latency_seconds": round(evaluation.latency_seconds, 2),
        "gate_failures": evaluation.gate_result.failures,
        "failure_modes": [
            mode
            for judge in evaluation.judge_outputs[:3]
            for mode in judge.failure_modes[:3]
        ],
        "judge_summaries": [
            truncate_text(judge.reasoning_summary, 280) for judge in evaluation.judge_outputs[:2]
        ],
        "sample_transcripts": [
            {
                "task_id": transcript.task_id,
                "student": truncate_text(transcript.student_message, 220),
                "tutor": truncate_text(transcript.tutor_response, 260),
            }
            for transcript in evaluation.transcripts[:2]
        ],
    }


def summarize_failure_modes(history: list[CandidateEvaluation]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in history:
        for failure in item.gate_result.failures:
            counter[failure] += 1
        for judge in item.judge_outputs:
            for mode in judge.failure_modes:
                counter[mode] += 1
    return dict(counter.most_common(10))


def truncate_text(text: str, max_chars: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3] + "..."
