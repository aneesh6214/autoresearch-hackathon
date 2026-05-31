from __future__ import annotations

from .config import ModelSettings
from .llm import LLMClient
from .schema import EvalTask, JudgeOutput, MetricScores, TutorTranscript


JUDGE_SYSTEM = """You are an adversarial evaluator for AI tutoring.

Score the tutor response against tutoring behavior, not generic helpfulness.
Prefer responses that diagnose the student's state, preserve student agency,
avoid answer leakage, and provide a useful next step. Penalize responses that
sound polished while missing the misconception, dumping answers, overusing vague
Socratic questioning, hallucinating, or refusing when explanation is appropriate."""


class TutorEvaluator:
    def evaluate(self, task: EvalTask, transcript: TutorTranscript) -> JudgeOutput:
        raise NotImplementedError


class LLMJudgeEvaluator(TutorEvaluator):
    def __init__(self, llm: LLMClient, settings: ModelSettings) -> None:
        self.llm = llm
        self.settings = settings

    def evaluate(self, task: EvalTask, transcript: TutorTranscript) -> JudgeOutput:
        response = self.llm.complete_json_response(
            model=self.settings.judge_model,
            system=JUDGE_SYSTEM,
            user=render_judge_prompt(task, transcript),
            reasoning_effort=self.settings.judge_reasoning_effort,
            text_verbosity=self.settings.text_verbosity,
            max_output_tokens=self.settings.max_output_tokens,
        )
        data = response.data
        scores_data = data.get("scores", data)
        return JudgeOutput(
            task_id=task.task_id,
            scores=MetricScores(**scores_data),
            reasoning_summary=str(data.get("reasoning_summary", "")),
            failure_modes=list(data.get("failure_modes", [])),
            token_usage=response.usage,
        )


class HeuristicTutorEvaluator(TutorEvaluator):
    """Small deterministic evaluator for tests and pipeline dry runs.

    It is intentionally simple and should not be used for real scoring.
    """

    def evaluate(self, task: EvalTask, transcript: TutorTranscript) -> JudgeOutput:
        text = transcript.tutor_response.lower()
        asks_question = "?" in text
        gives_next_step = any(word in text for word in ("try", "next", "check", "look at"))
        leaks_answer = task.answer_leakage_risk and any(
            phrase in text for phrase in ("the answer is", "final answer", "therefore x =")
        )
        too_long = len(transcript.tutor_response.split()) > 180
        identifies_error = any(word in text for word in ("mistake", "error", "because", "confus"))
        correctness = 0.7 if not leaks_answer else 0.45
        pedagogy = 0.75 if asks_question or gives_next_step else 0.5
        scores = MetricScores(
            correctness=correctness,
            pedagogy=pedagogy,
            student_understanding=0.7 if gives_next_step else 0.5,
            mistake_identification=0.7 if identifies_error else 0.45,
            mistake_location=0.65 if identifies_error else 0.45,
            hint_quality=0.75 if gives_next_step else 0.45,
            actionability=0.75 if gives_next_step else 0.45,
            cognitive_load=0.35 if too_long else 0.75,
            tone=0.7,
            answer_leakage=0.8 if leaks_answer else 0.1,
            harm_rate=0.6 if leaks_answer else 0.1,
            hallucination=0.1,
            verbosity_overload=0.7 if too_long else 0.1,
            inappropriate_refusal=0.1,
        )
        failures = []
        if leaks_answer:
            failures.append("answer_leakage")
        if too_long:
            failures.append("verbosity_overload")
        if not identifies_error:
            failures.append("weak_mistake_diagnosis")
        return JudgeOutput(
            task_id=task.task_id,
            scores=scores,
            reasoning_summary="Heuristic dry-run score.",
            failure_modes=failures,
        )


def render_judge_prompt(task: EvalTask, transcript: TutorTranscript) -> str:
    return f"""Evaluate this tutoring response.

Task ID: {task.task_id}
Benchmark: {task.benchmark}
Subject: {task.subject}
Target concept: {task.target_concept}
Answer-leakage risk: {task.answer_leakage_risk}

Student message:
{task.student_message}

Expected behavior:
{task.expected_behavior}

Rubric:
{task.rubric}

Tutor response:
{transcript.tutor_response}

Return JSON with this shape:
{{
  "scores": {{
    "correctness": 0.0,
    "pedagogy": 0.0,
    "student_understanding": 0.0,
    "mistake_identification": 0.0,
    "mistake_location": 0.0,
    "hint_quality": 0.0,
    "actionability": 0.0,
    "cognitive_load": 0.0,
    "tone": 0.0,
    "tutorbench_rubric_pass": 0.0,
    "private_eval_score": 0.0,
    "answer_leakage": 0.0,
    "harm_rate": 0.0,
    "hallucination": 0.0,
    "verbosity_overload": 0.0,
    "inappropriate_refusal": 0.0
  }},
  "reasoning_summary": "brief evaluator rationale",
  "failure_modes": ["short labels"]
}}

Quality metrics use 1.0 as best. Risk metrics use 0.0 as best."""
