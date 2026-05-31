from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ReasoningEffort = str


@dataclass(frozen=True)
class ModelSettings:
    tutor_model: str
    research_model: str
    judge_model: str
    tutor_reasoning_effort: ReasoningEffort
    research_reasoning_effort: ReasoningEffort
    judge_reasoning_effort: ReasoningEffort
    text_verbosity: str
    max_output_tokens: int


@dataclass(frozen=True)
class RuntimeSettings:
    modal_openai_secret_name: str
    wall_clock_minutes: int = 180
    smoke_minutes: int = 10
    search_minutes: int = 95
    checkpoint_minutes: int = 40
    final_minutes: int = 25
    freeze_minutes: int = 10
    modal_parallelism: int = 8
    default_initial_candidates: int = 10
    default_followup_candidates: int = 18
    checkpoint_candidate_count: int = 4
    max_cost_per_candidate_usd: float = 10.0
    max_latency_per_candidate_seconds: float = 180.0


@dataclass(frozen=True)
class AppSettings:
    model: ModelSettings
    runtime: RuntimeSettings
    project_root: Path


def load_settings(project_root: Path | None = None) -> AppSettings:
    root = project_root or Path.cwd()
    load_dotenv(root / ".env")

    model = ModelSettings(
        tutor_model=os.getenv("OPENAI_TUTOR_MODEL", "gpt-5.5"),
        research_model=os.getenv("OPENAI_RESEARCH_MODEL", "gpt-5.5"),
        judge_model=os.getenv("OPENAI_JUDGE_MODEL", "gpt-5.5"),
        tutor_reasoning_effort=os.getenv("OPENAI_TUTOR_REASONING_EFFORT", "medium"),
        research_reasoning_effort=os.getenv("OPENAI_RESEARCH_REASONING_EFFORT", "medium"),
        judge_reasoning_effort=os.getenv("OPENAI_JUDGE_REASONING_EFFORT", "medium"),
        text_verbosity=os.getenv("OPENAI_TEXT_VERBOSITY", "medium"),
        max_output_tokens=int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "8192")),
    )
    runtime = RuntimeSettings(
        modal_openai_secret_name=os.getenv("MODAL_OPENAI_SECRET_NAME", "openai-api-key"),
        modal_parallelism=int(os.getenv("MODAL_PARALLELISM", "8")),
        max_cost_per_candidate_usd=float(os.getenv("MAX_COST_PER_CANDIDATE_USD", "10")),
        max_latency_per_candidate_seconds=float(
            os.getenv("MAX_LATENCY_PER_CANDIDATE_SECONDS", "180")
        ),
    )
    return AppSettings(model=model, runtime=runtime, project_root=root)


def require_openai_key() -> str:
    load_dotenv()
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is required for non-dry-run model calls.")
    return key
