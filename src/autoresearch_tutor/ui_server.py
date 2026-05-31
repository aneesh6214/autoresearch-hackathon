from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import load_settings
from .llm import OpenAIResponsesClient
from .schema import EvalTask, StrategySpec
from .strategy import StrategyExecutor


PROJECT_ROOT = Path.cwd()
RUN_DIR = Path(os.getenv("AUTORESEARCH_RUN_DIR", "")) if os.getenv("AUTORESEARCH_RUN_DIR") else None

app = FastAPI(title="Autoresearch Tutor UI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatConfig(BaseModel):
    subject: str = "math"
    target_concept: str = ""
    tutoring_goal: str = (
        "Use the optimized tutor strategy. Prioritize diagnosis, low answer leakage, "
        "and one concrete next question."
    )


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    config: ChatConfig = Field(default_factory=ChatConfig)


class ChatResponse(BaseModel):
    reply: str
    candidate_id: str
    architecture: str
    model_call_count: int
    latency_seconds: float
    token_usage: dict[str, int]


def get_run_dir() -> Path:
    if RUN_DIR is not None:
        return RUN_DIR
    candidates = [
        path
        for path in (PROJECT_ROOT / "runs").glob("full-resume-*")
        if (path / "winner_strategy.json").exists()
    ]
    if not candidates:
        raise RuntimeError("No completed run with winner_strategy.json found.")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def load_winner_strategy() -> StrategySpec:
    return StrategySpec.model_validate_json((get_run_dir() / "winner_strategy.json").read_text())


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "run_dir": str(get_run_dir())}


@app.get("/api/run")
def run_summary() -> dict[str, object]:
    run_dir = get_run_dir()
    summary = json.loads((run_dir / "summary.json").read_text())
    strategy = json.loads((run_dir / "winner_strategy.json").read_text())
    manifest_path = PROJECT_ROOT / "data/manifests/benchmark_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    return {
        "run_dir": str(run_dir),
        "summary": summary,
        "strategy": strategy,
        "benchmark_manifest": manifest,
    }


@app.post("/api/chat")
def chat(request: ChatRequest) -> ChatResponse:
    settings = load_settings(PROJECT_ROOT)
    strategy = load_winner_strategy()
    executor = StrategyExecutor(
        llm=OpenAIResponsesClient(settings.model),
        settings=settings.model,
    )
    task = EvalTask(
        task_id=f"ui_{uuid4().hex[:12]}",
        benchmark="ManualUI",
        split="ui",
        subject=request.config.subject,
        student_message=render_chat_task(request),
        target_concept=request.config.target_concept,
        expected_behavior=request.config.tutoring_goal,
        rubric="Manual UI demo conversation; no benchmark scoring is run for this turn.",
        answer_leakage_risk=True,
    )
    transcript = executor.run(strategy, task)
    return ChatResponse(
        reply=transcript.tutor_response,
        candidate_id=strategy.candidate_id,
        architecture=str(strategy.response_architecture),
        model_call_count=transcript.model_call_count,
        latency_seconds=transcript.latency_seconds,
        token_usage=transcript.token_usage,
    )


def render_chat_task(request: ChatRequest) -> str:
    rendered_messages = "\n".join(
        f"{message.role.title()}: {message.content.strip()}" for message in request.messages
    )
    return (
        f"Conversation so far:\n{rendered_messages}\n\n"
        "Write the next tutor response to the student's latest message. Stay natural and concise."
    )
