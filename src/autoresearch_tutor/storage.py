from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from .schema import CandidateEvaluation, StrategySpec


class RunStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def write_strategy(self, strategy: StrategySpec) -> Path:
        path = self.root / "strategies" / f"{strategy.candidate_id}.json"
        self._write_model(path, strategy)
        return path

    def write_evaluation(self, evaluation: CandidateEvaluation) -> Path:
        path = self.root / "evaluations" / f"{evaluation.phase}_{evaluation.candidate_id}.json"
        self._write_model(path, evaluation)
        return path

    def write_history(self, evaluations: list[CandidateEvaluation]) -> Path:
        path = self.root / "history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as handle:
            for evaluation in evaluations:
                handle.write(evaluation.model_dump_json() + "\n")
        return path

    def write_summary(self, data: dict) -> Path:
        path = self.root / "summary.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str))
        return path

    @staticmethod
    def _write_model(path: Path, model: BaseModel) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(model.model_dump_json(indent=2))
