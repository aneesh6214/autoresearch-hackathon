from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchBudget:
    search_phase_minutes: float
    modal_parallelism: int
    measured_minutes_per_candidate: float | None = None
    default_candidate_budget: int = 24

    def candidate_budget(self) -> int:
        if not self.measured_minutes_per_candidate or self.measured_minutes_per_candidate <= 0:
            return self.default_candidate_budget
        budget = int(
            (self.search_phase_minutes * max(self.modal_parallelism, 1))
            // self.measured_minutes_per_candidate
        )
        return max(1, budget)

    def split_initial_followup(self) -> tuple[int, int]:
        total = self.candidate_budget()
        initial = min(12, max(4, total // 3))
        followup = max(0, total - initial)
        return initial, followup
