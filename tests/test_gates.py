from autoresearch_tutor.gates import GateChecker
from autoresearch_tutor.schema import MetricScores


def test_gate_rejects_answer_leakage_regression() -> None:
    baseline = MetricScores.neutral().model_copy(update={"answer_leakage": 0.1})
    candidate = MetricScores.neutral().model_copy(update={"answer_leakage": 0.4})

    result = GateChecker().check(
        candidate=candidate,
        baseline=baseline,
        latency_seconds=1.0,
        cost_usd=0.01,
    )

    assert not result.passed
    assert any("answer leakage" in failure for failure in result.failures)


def test_gate_tolerates_tiny_judge_noise_on_risk_metrics() -> None:
    baseline = MetricScores.neutral().model_copy(update={"verbosity_overload": 0.0})
    candidate = MetricScores.neutral().model_copy(update={"verbosity_overload": 0.05})

    result = GateChecker().check(
        candidate=candidate,
        baseline=baseline,
        latency_seconds=1.0,
        cost_usd=0.01,
    )

    assert result.passed


def test_gate_accepts_non_regressing_candidate() -> None:
    baseline = MetricScores.neutral().model_copy(update={"answer_leakage": 0.1})
    candidate = MetricScores.neutral().model_copy(
        update={"pedagogy": 0.7, "student_understanding": 0.7, "answer_leakage": 0.1}
    )

    result = GateChecker().check(
        candidate=candidate,
        baseline=baseline,
        latency_seconds=1.0,
        cost_usd=0.01,
    )

    assert result.passed
