from autoresearch_tutor.schema import ResponseArchitecture, StrategySpec


def test_multicall_architecture_sets_required_prompts() -> None:
    strategy = StrategySpec(
        response_architecture=ResponseArchitecture.PLAN_THEN_ANSWER,
        tutor_policy="Diagnose first, then tutor.",
    )

    assert strategy.max_model_calls == 2
    assert strategy.hidden_planning_prompt is not None


def test_self_critique_strategy_sets_critique_prompt() -> None:
    strategy = StrategySpec(
        response_architecture=ResponseArchitecture.SELF_CRITIQUE_REVISE,
        tutor_policy="Draft and revise for tutoring quality.",
    )

    assert strategy.max_model_calls == 2
    assert strategy.self_critique_prompt is not None
