from autoresearch_tutor.budget import SearchBudget
from autoresearch_tutor.runner import estimate_cost_usd
from autoresearch_tutor.schema import (
    JudgeOutput,
    MetricScores,
    ResponseArchitecture,
    TutorTranscript,
)


def test_candidate_budget_uses_measured_runtime_and_parallelism() -> None:
    budget = SearchBudget(
        search_phase_minutes=90,
        modal_parallelism=8,
        measured_minutes_per_candidate=12,
    )

    assert budget.candidate_budget() == 60


def test_candidate_budget_uses_default_without_measurement() -> None:
    budget = SearchBudget(
        search_phase_minutes=90,
        modal_parallelism=8,
        measured_minutes_per_candidate=None,
        default_candidate_budget=24,
    )

    assert budget.candidate_budget() == 24


def test_cost_estimate_uses_tutor_and_judge_tokens(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_INPUT_USD_PER_1M_TOKENS", "10")
    monkeypatch.setenv("OPENAI_OUTPUT_USD_PER_1M_TOKENS", "20")
    transcript = TutorTranscript(
        candidate_id="candidate",
        task_id="task",
        architecture=ResponseArchitecture.SINGLE_PASS,
        student_message="student",
        tutor_response="tutor",
        token_usage={"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500},
    )
    judge = JudgeOutput(
        task_id="task",
        scores=MetricScores.neutral(),
        reasoning_summary="ok",
        token_usage={"input_tokens": 2000, "output_tokens": 250, "total_tokens": 2250},
    )

    assert estimate_cost_usd([transcript], [judge]) == 0.045
