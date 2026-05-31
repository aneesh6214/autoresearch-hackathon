from autoresearch_tutor.constraints import strategy_constraint_failures
from autoresearch_tutor.schema import StrategySpec


def test_strategy_constraints_reject_benchmark_references() -> None:
    strategy = StrategySpec(
        tutor_policy="Optimize for MathTutorBench and judge approval.",
    )

    failures = strategy_constraint_failures(strategy)

    assert failures
    assert any("mathtutorbench" in failure for failure in failures)
