from __future__ import annotations

from .schema import StrategySpec


FORBIDDEN_STRATEGY_TERMS = (
    "mathtutorbench",
    "tutorbench",
    "safetutors",
    "private hidden eval",
    "hidden eval",
    "benchmark score",
    "judge approval",
    "evaluator approval",
    "rubric gaming",
)


def strategy_constraint_failures(strategy: StrategySpec) -> list[str]:
    text = "\n".join(
        value
        for value in (
            strategy.tutor_policy,
            strategy.output_structure,
            strategy.hidden_planning_prompt or "",
            strategy.self_critique_prompt or "",
            " ".join(example.student + " " + example.tutor for example in strategy.few_shot_examples),
        )
        if value
    ).lower()
    failures = [
        f"strategy references forbidden term: {term}"
        for term in FORBIDDEN_STRATEGY_TERMS
        if term in text
    ]
    if strategy.max_model_calls > 2:
        failures.append("strategy exceeds maximum model-call budget")
    if len(strategy.few_shot_examples) > 3:
        failures.append("strategy exceeds few-shot example limit")
    return failures
