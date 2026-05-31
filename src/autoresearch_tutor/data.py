from __future__ import annotations

import json
from pathlib import Path

from .schema import EvalTask


def load_tasks(path: Path) -> list[EvalTask]:
    if not path.exists():
        raise FileNotFoundError(f"Eval task file not found: {path}")
    if path.suffix == ".jsonl":
        return load_tasks_jsonl(path)
    if path.suffix == ".json":
        data = json.loads(path.read_text())
        if not isinstance(data, list):
            raise ValueError(f"Expected list in {path}")
        return [EvalTask(**item) for item in data]
    raise ValueError(f"Unsupported task file format: {path.suffix}")


def load_tasks_jsonl(path: Path) -> list[EvalTask]:
    tasks: list[EvalTask] = []
    for line_no, line in enumerate(path.read_text().splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            tasks.append(EvalTask(**json.loads(stripped)))
        except Exception as exc:
            raise ValueError(f"Invalid task JSON at {path}:{line_no}") from exc
    return tasks


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for record in records:
            handle.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")
