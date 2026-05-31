from __future__ import annotations

from .schema import GenerationAction, ResponseArchitecture, StrategySpec


BASELINE_POLICY = """Diagnose the student's current understanding before teaching.
If the student made a mistake, identify the relevant step and explain why it matters.
Avoid giving the final answer immediately when the student can still productively try.
Give one targeted hint or one small worked step, then ask the student to continue.
Use concise, supportive language and avoid long lectures."""


def make_baseline_strategy() -> StrategySpec:
    return StrategySpec(
        candidate_id="baseline",
        generation_action=GenerationAction.BASELINE,
        response_architecture=ResponseArchitecture.SINGLE_PASS,
        tutor_policy=BASELINE_POLICY,
        output_structure=(
            "Brief diagnosis, one targeted hint or micro-step, and one concrete "
            "question or next action for the student."
        ),
        rationale="Manual baseline strategy for the first experiment.",
        max_model_calls=1,
    )
