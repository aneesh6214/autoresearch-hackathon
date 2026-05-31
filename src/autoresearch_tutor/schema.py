from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ResponseArchitecture(StrEnum):
    SINGLE_PASS = "single_pass"
    PLAN_THEN_ANSWER = "plan_then_answer"
    SELF_CRITIQUE_REVISE = "self_critique_revise"
    DIAGNOSE_THEN_TUTOR = "diagnose_then_tutor"


class GenerationAction(StrEnum):
    BASELINE = "baseline"
    SEED = "seed"
    MUTATION = "mutation"
    RECOMBINATION = "recombination"
    REPAIR = "repair"
    ABLATION = "ablation"


class EvalPhase(StrEnum):
    SMOKE = "smoke"
    INNER_LOOP = "inner_loop"
    CHECKPOINT = "checkpoint"
    FINAL = "final"


class CandidateStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    REJECTED = "rejected"
    ERROR = "error"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class FewShotExample(BaseModel):
    student: str
    tutor: str
    notes: str = ""


class StrategySpec(BaseModel):
    """Bounded tutor strategy program searched by the autoresearch agent."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(default_factory=lambda: new_id("cand"))
    parent_candidate_ids: list[str] = Field(default_factory=list)
    generation_action: GenerationAction = GenerationAction.SEED
    response_architecture: ResponseArchitecture = ResponseArchitecture.SINGLE_PASS
    tutor_policy: str
    output_structure: str = "Natural student-facing response ending with one concrete next step."
    few_shot_examples: list[FewShotExample] = Field(default_factory=list, max_length=3)
    hidden_planning_prompt: str | None = None
    self_critique_prompt: str | None = None
    rationale: str = ""
    max_model_calls: int = Field(default=1, ge=1, le=2)
    created_at: datetime = Field(default_factory=now_utc)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tutor_policy", "output_structure")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text fields must be non-empty")
        return value

    @model_validator(mode="after")
    def architecture_requires_calls(self) -> StrategySpec:
        multi_call_architectures = {
            ResponseArchitecture.PLAN_THEN_ANSWER,
            ResponseArchitecture.SELF_CRITIQUE_REVISE,
            ResponseArchitecture.DIAGNOSE_THEN_TUTOR,
        }
        if self.response_architecture in multi_call_architectures and self.max_model_calls < 2:
            self.max_model_calls = 2
        if self.response_architecture == ResponseArchitecture.SELF_CRITIQUE_REVISE and not self.self_critique_prompt:
            self.self_critique_prompt = (
                "Critique the draft for tutoring failures: answer leakage, missed misconception, "
                "weak next step, excessive verbosity, factual errors, or poor student agency."
            )
        if self.response_architecture in {
            ResponseArchitecture.PLAN_THEN_ANSWER,
            ResponseArchitecture.DIAGNOSE_THEN_TUTOR,
        } and not self.hidden_planning_prompt:
            self.hidden_planning_prompt = (
                "Diagnose the student's state, likely misconception, answer-leakage risk, "
                "and the most useful next tutoring move."
            )
        return self


class EvalTask(BaseModel):
    model_config = ConfigDict(extra="allow")

    task_id: str
    benchmark: str
    split: str = "inner_loop"
    subject: str = "math"
    student_message: str
    target_concept: str = ""
    expected_behavior: str = ""
    rubric: str = ""
    answer_leakage_risk: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class TutorTranscript(BaseModel):
    candidate_id: str
    task_id: str
    architecture: ResponseArchitecture
    student_message: str
    tutor_response: str
    hidden_plan: str | None = None
    draft_response: str | None = None
    critique: str | None = None
    model_call_count: int = 1
    latency_seconds: float = 0.0
    token_usage: dict[str, int] = Field(default_factory=dict)


class MetricScores(BaseModel):
    """Normalized component scores.

    Positive quality metrics use 0.0=bad and 1.0=good.
    Risk metrics use 0.0=no observed risk and 1.0=severe risk.
    """

    correctness: float = Field(ge=0, le=1)
    pedagogy: float = Field(ge=0, le=1)
    student_understanding: float = Field(ge=0, le=1)
    mistake_identification: float = Field(ge=0, le=1)
    mistake_location: float = Field(ge=0, le=1)
    hint_quality: float = Field(ge=0, le=1)
    actionability: float = Field(ge=0, le=1)
    cognitive_load: float = Field(ge=0, le=1)
    tone: float = Field(ge=0, le=1)
    tutorbench_rubric_pass: float = Field(default=0.0, ge=0, le=1)
    private_eval_score: float = Field(default=0.0, ge=0, le=1)
    answer_leakage: float = Field(default=0.0, ge=0, le=1)
    harm_rate: float = Field(default=0.0, ge=0, le=1)
    hallucination: float = Field(default=0.0, ge=0, le=1)
    verbosity_overload: float = Field(default=0.0, ge=0, le=1)
    inappropriate_refusal: float = Field(default=0.0, ge=0, le=1)

    @classmethod
    def neutral(cls) -> MetricScores:
        return cls(
            correctness=0.5,
            pedagogy=0.5,
            student_understanding=0.5,
            mistake_identification=0.5,
            mistake_location=0.5,
            hint_quality=0.5,
            actionability=0.5,
            cognitive_load=0.5,
            tone=0.5,
        )

    @classmethod
    def mean(cls, scores: list[MetricScores]) -> MetricScores:
        if not scores:
            return cls.neutral()
        data: dict[str, float] = {}
        for name in cls.model_fields:
            data[name] = sum(getattr(score, name) for score in scores) / len(scores)
        return cls(**data)

    @property
    def display_score(self) -> float:
        return (
            0.50 * self.pedagogy
            + 0.20 * self.student_understanding
            + 0.20 * self.tutorbench_rubric_pass
            + 0.10 * self.private_eval_score
        )

    @property
    def core_quality_score(self) -> float:
        return (
            self.correctness
            + self.pedagogy
            + self.student_understanding
            + self.mistake_identification
            + self.mistake_location
            + self.hint_quality
            + self.actionability
            + self.cognitive_load
            + self.tone
        ) / 9.0


class JudgeOutput(BaseModel):
    task_id: str
    scores: MetricScores
    reasoning_summary: str
    failure_modes: list[str] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)


class GateResult(BaseModel):
    passed: bool
    failures: list[str] = Field(default_factory=list)


class CandidateEvaluation(BaseModel):
    candidate_id: str
    phase: EvalPhase
    status: CandidateStatus
    strategy: StrategySpec
    aggregate_scores: MetricScores
    gate_result: GateResult
    transcripts: list[TutorTranscript] = Field(default_factory=list)
    judge_outputs: list[JudgeOutput] = Field(default_factory=list)
    benchmark_subset_ids: list[str] = Field(default_factory=list)
    rejection_reason: str | None = None
    cost_usd: float = 0.0
    latency_seconds: float = 0.0
    created_at: datetime = Field(default_factory=now_utc)


class ResearchDecision(BaseModel):
    action: GenerationAction
    rationale: str
    target_failure_mode: str | None = None
    parent_candidate_ids: list[str] = Field(default_factory=list)
    strategy: StrategySpec | None = None


class RunSummary(BaseModel):
    run_id: str
    started_at: datetime
    ended_at: datetime | None = None
    baseline_candidate_id: str
    winner_candidate_id: str | None = None
    candidate_count: int = 0
    rejected_count: int = 0
    notes: list[str] = Field(default_factory=list)
