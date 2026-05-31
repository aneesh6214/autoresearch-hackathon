from __future__ import annotations

import time

from .config import ModelSettings
from .llm import LLMClient
from .schema import EvalTask, ResponseArchitecture, StrategySpec, TutorTranscript


BASE_TUTOR_CONTRACT = """You are an expert tutor.

Optimize for learning, not answer dumping. Diagnose the student's current state,
address misconceptions accurately, preserve student agency, and provide the most
useful next step. Do not mention benchmark rubrics or evaluator behavior."""


class StrategyExecutor:
    def __init__(self, llm: LLMClient, settings: ModelSettings) -> None:
        self.llm = llm
        self.settings = settings

    def run(self, strategy: StrategySpec, task: EvalTask) -> TutorTranscript:
        start = time.perf_counter()
        if strategy.response_architecture == ResponseArchitecture.SINGLE_PASS:
            transcript = self._single_pass(strategy, task)
        elif strategy.response_architecture == ResponseArchitecture.PLAN_THEN_ANSWER:
            transcript = self._plan_then_answer(strategy, task)
        elif strategy.response_architecture == ResponseArchitecture.SELF_CRITIQUE_REVISE:
            transcript = self._self_critique_revise(strategy, task)
        elif strategy.response_architecture == ResponseArchitecture.DIAGNOSE_THEN_TUTOR:
            transcript = self._diagnose_then_tutor(strategy, task)
        else:
            raise ValueError(f"Unsupported architecture: {strategy.response_architecture}")
        transcript.latency_seconds = time.perf_counter() - start
        return transcript

    def _single_pass(self, strategy: StrategySpec, task: EvalTask) -> TutorTranscript:
        response = self.llm.complete_text(
            model=self.settings.tutor_model,
            system=render_tutor_system_prompt(strategy),
            user=render_student_task(task),
            reasoning_effort=self.settings.tutor_reasoning_effort,
            text_verbosity=self.settings.text_verbosity,
            max_output_tokens=self.settings.max_output_tokens,
        )
        return TutorTranscript(
            candidate_id=strategy.candidate_id,
            task_id=task.task_id,
            architecture=strategy.response_architecture,
            student_message=task.student_message,
            tutor_response=response.text,
            model_call_count=1,
            token_usage=response.usage,
        )

    def _plan_then_answer(self, strategy: StrategySpec, task: EvalTask) -> TutorTranscript:
        plan = self.llm.complete_text(
            model=self.settings.tutor_model,
            system=render_tutor_system_prompt(strategy),
            user=f"{strategy.hidden_planning_prompt}\n\n{render_student_task(task)}",
            reasoning_effort=self.settings.tutor_reasoning_effort,
            text_verbosity="low",
            max_output_tokens=self.settings.max_output_tokens,
        )
        answer = self.llm.complete_text(
            model=self.settings.tutor_model,
            system=render_tutor_system_prompt(strategy),
            user=(
                "Use the hidden plan to write only the student-facing tutor response. "
                "Do not reveal hidden planning.\n\n"
                f"Hidden plan:\n{plan.text}\n\n{render_student_task(task)}"
            ),
            reasoning_effort=self.settings.tutor_reasoning_effort,
            text_verbosity=self.settings.text_verbosity,
            max_output_tokens=self.settings.max_output_tokens,
        )
        return TutorTranscript(
            candidate_id=strategy.candidate_id,
            task_id=task.task_id,
            architecture=strategy.response_architecture,
            student_message=task.student_message,
            hidden_plan=plan.text,
            tutor_response=answer.text,
            model_call_count=2,
            token_usage=_sum_usage(plan.usage, answer.usage),
        )

    def _self_critique_revise(self, strategy: StrategySpec, task: EvalTask) -> TutorTranscript:
        draft = self.llm.complete_text(
            model=self.settings.tutor_model,
            system=render_tutor_system_prompt(strategy),
            user=render_student_task(task),
            reasoning_effort=self.settings.tutor_reasoning_effort,
            text_verbosity=self.settings.text_verbosity,
            max_output_tokens=self.settings.max_output_tokens,
        )
        final = self.llm.complete_text(
            model=self.settings.tutor_model,
            system=render_tutor_system_prompt(strategy),
            user=(
                f"{strategy.self_critique_prompt}\n\n"
                f"Student task:\n{render_student_task(task)}\n\n"
                f"Draft tutor response:\n{draft.text}\n\n"
                "Return the revised student-facing tutor response only."
            ),
            reasoning_effort=self.settings.tutor_reasoning_effort,
            text_verbosity=self.settings.text_verbosity,
            max_output_tokens=self.settings.max_output_tokens,
        )
        return TutorTranscript(
            candidate_id=strategy.candidate_id,
            task_id=task.task_id,
            architecture=strategy.response_architecture,
            student_message=task.student_message,
            draft_response=draft.text,
            critique=strategy.self_critique_prompt,
            tutor_response=final.text,
            model_call_count=2,
            token_usage=_sum_usage(draft.usage, final.usage),
        )

    def _diagnose_then_tutor(self, strategy: StrategySpec, task: EvalTask) -> TutorTranscript:
        diagnosis = self.llm.complete_text(
            model=self.settings.tutor_model,
            system=render_tutor_system_prompt(strategy),
            user=(
                "Classify the student's current state and likely misconception. "
                "Return a concise hidden diagnosis only.\n\n"
                f"{render_student_task(task)}"
            ),
            reasoning_effort=self.settings.tutor_reasoning_effort,
            text_verbosity="low",
            max_output_tokens=self.settings.max_output_tokens,
        )
        answer = self.llm.complete_text(
            model=self.settings.tutor_model,
            system=render_tutor_system_prompt(strategy),
            user=(
                "Use this hidden diagnosis to tutor the student. Do not reveal labels unless "
                "they help the student understand their mistake.\n\n"
                f"Hidden diagnosis:\n{diagnosis.text}\n\n{render_student_task(task)}"
            ),
            reasoning_effort=self.settings.tutor_reasoning_effort,
            text_verbosity=self.settings.text_verbosity,
            max_output_tokens=self.settings.max_output_tokens,
        )
        return TutorTranscript(
            candidate_id=strategy.candidate_id,
            task_id=task.task_id,
            architecture=strategy.response_architecture,
            student_message=task.student_message,
            hidden_plan=diagnosis.text,
            tutor_response=answer.text,
            model_call_count=2,
            token_usage=_sum_usage(diagnosis.usage, answer.usage),
        )


def render_tutor_system_prompt(strategy: StrategySpec) -> str:
    examples = ""
    if strategy.few_shot_examples:
        rendered = []
        for idx, example in enumerate(strategy.few_shot_examples, start=1):
            rendered.append(
                f"Example {idx}\nStudent: {example.student}\nTutor: {example.tutor}"
            )
        examples = "\n\nFew-shot tutoring examples:\n" + "\n\n".join(rendered)
    return (
        f"{BASE_TUTOR_CONTRACT}\n\n"
        f"Tutor policy:\n{strategy.tutor_policy}\n\n"
        f"Output structure:\n{strategy.output_structure}"
        f"{examples}"
    )


def render_student_task(task: EvalTask) -> str:
    parts = [f"Student message:\n{task.student_message}"]
    if task.target_concept:
        parts.append(f"Target concept:\n{task.target_concept}")
    if task.expected_behavior:
        parts.append(f"Expected tutor behavior:\n{task.expected_behavior}")
    if task.answer_leakage_risk:
        parts.append("This task has answer-leakage risk. Tutor carefully.")
    return "\n\n".join(parts)


def _sum_usage(*usages: dict[str, int]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for usage in usages:
        for key, value in usage.items():
            merged[key] = merged.get(key, 0) + int(value)
    return merged
