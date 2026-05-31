# Hackathon Tutor Autoresearch Experiment

## Goal

Build an autoresearch agent that improves an AI tutor under a strict three-hour wall-clock budget.

The experiment should support this claim:

> We built a bounded research agent that proposes tutor strategies, runs benchmark experiments, analyzes failures, chooses the next search step, rejects unsafe candidates, and validates the winner on held-out evals.

The experiment should not claim:

> We proved that students learn more.

The benchmark suite measures tutor behavior, not actual student learning outcomes.

## Core Methodology

This is not just prompt optimization. The optimized artifact is a **tutor strategy program**.

A tutor strategy program is a small configuration of existing primitives:

- response architecture
- tutor policy prompts
- optional hidden planning step
- optional self-critique or revision step
- few-shot tutoring examples
- output structure
- answer-boundary and scaffolding rules

The evaluator, benchmarks, scoring rules, and safety gates are fixed. The research agent can propose and revise tutor strategies, but it cannot edit the yardstick.

## Autoresearch Agent

The research agent controls the search.

Inputs:

- current best strategy
- full candidate history
- benchmark scores
- safety gate failures
- representative transcripts
- cost and latency
- time remaining

Allowed research actions:

- generate a new candidate strategy
- mutate a high-performing strategy
- recombine two high-performing strategies
- repair the worst failure mode of a strategy
- ablate a component from a strategy
- choose a targeted public benchmark slice for diagnosis
- promote candidates to checkpoint evaluation
- stop search and freeze the current winner

Forbidden research actions:

- edit benchmark examples
- edit judge prompts or scoring weights during the run
- inspect or train against the private hidden eval
- hardcode benchmark answers
- optimize for judge approval language
- change the safety gates after seeing results
- continue searching after the three-hour budget expires

## Candidate Strategy Space

Candidates may vary across these dimensions.

### Response Architecture

Allowed architectures:

- `single_pass`: one tutor response from the student message.
- `plan_then_answer`: hidden diagnosis/planning pass, then student-facing answer.
- `self_critique_revise`: draft response, critique for tutoring failures, then revise.
- `diagnose_then_tutor`: classify student state or misconception, then tutor using that diagnosis.

### Tutor Policy

The policy may specify:

- how to diagnose misconceptions
- when to ask a guiding question
- when to give a hint
- when to explain directly
- how much work to show
- how to avoid answer leakage
- how to manage cognitive load
- how to preserve student agency

### Few-Shot Examples

The strategy may include 0-3 short tutoring examples.

Few-shot examples must be synthetic or team-authored. They must not be copied from benchmark examples or hidden eval examples.

### Output Structure

The strategy may choose a response structure, such as:

- short diagnosis plus next step
- hint-first response
- misconception correction plus check question
- one worked micro-step plus student handoff

The output structure is allowed to change, but the final answer must remain natural for a student.

### Inference Constraints

To keep the search practical:

- maximum 2 model calls per tutor response
- fixed tutor model
- fixed judge model
- fixed temperature
- fixed max tokens
- no retrieval
- no external tools
- no fine-tuning
- no model routing

This gives the research agent more power than prompt search while keeping the implementation and runtime bounded.

## Three-Hour Budget

The optimization loop has a hard maximum runtime of three hours.

Recommended allocation:

| Time | Phase | Work |
| --- | --- | --- |
| 0:00-0:10 | Smoke | Run baseline and one candidate on a tiny eval to verify the pipeline and estimate candidate runtime. |
| 0:10-1:45 | Search | Generate, evaluate, gate, repair, mutate, recombine, and ablate candidates on cheap benchmark subsets. |
| 1:45-2:25 | Checkpoint | Evaluate baseline plus top 3-4 candidates on larger MathTutorBench, TutorBench, and SafeTutors slices. |
| 2:25-2:50 | Final | Evaluate baseline and selected winner on the private hidden mini-eval. |
| 2:50-3:00 | Freeze | Save winner, transcripts, score table, rejection reasons, and demo artifacts. |

The loop stops generating new candidates at 1:45. Late candidates are discarded unless their evaluation has already completed.

The smoke phase estimates candidate runtime:

```text
candidate_budget =
  floor(search_phase_minutes * modal_parallelism / measured_minutes_per_candidate)
```

If runtime is unstable, default to:

- 8-12 initial candidates
- 12-24 follow-up candidates
- top 3-4 checkpoint candidates
- 1 final winner

## Search Policy

Use budget-aware successive halving.

1. Start with diverse candidates across response architectures.
2. Evaluate each on a cheap inner-loop slice.
3. Reject candidates that fail hard gates.
4. Keep a small frontier of valid candidates.
5. Ask the research agent to explain the frontier's main failure modes.
6. Generate the next batch using targeted repair, mutation, recombination, and ablation.
7. Spend larger evals only on candidates that survive cheap evals.
8. Freeze the best valid candidate before the final eval window.

The loop should optimize for benchmarked tutor behavior per unit time, not for the most complex strategy.

## Benchmark Plan

### Inner Loop

Run every candidate on:

- MathTutorBench subset
- SafeTutors subset

Purpose:

- MathTutorBench supplies the main tutoring-quality signal.
- SafeTutors rejects answer-dumping or pedagogically harmful policies.

### Checkpoint Eval

Run the baseline and top candidates on:

- larger MathTutorBench subset
- TutorBench text-only subset
- larger SafeTutors subset

Purpose:

- confirm generalization beyond the inner-loop slice
- catch math-only overfitting
- preserve safety constraints
- compare strategy complexity against quality gains

### Final Eval

Run only the baseline and selected winner on:

- checkpoint suite
- private hidden mini-eval

Purpose:

- choose the demo policy
- avoid public-benchmark overfitting
- produce the final before/after story

## Private Hidden Mini-Eval

Create 30-50 examples. Do not expose them to the research agent during search.

Required scenario types:

- student asks for the direct answer
- student is confidently wrong
- student makes an arithmetic error
- student makes a conceptual error
- student is confused but not wrong
- student gives incomplete work
- student uses the wrong formula
- student has the right answer for the wrong reason
- direct explanation is better than questioning
- Socratic questioning is useful

Each example should include:

- student message
- target concept
- expected tutor behavior
- answer-leakage risk
- rubric notes

## Gates

A candidate is rejected before ranking if any hard gate fails.

Hard gates:

- answer leakage increases over baseline
- SafeTutors harm rate increases over baseline
- correctness drops materially
- mistake identification drops below baseline
- mistake location drops below baseline
- hallucination or factuality failure increases
- response becomes too verbose or cognitively overloaded
- tutor refuses to explain when direct explanation is appropriate
- latency exceeds the configured demo budget
- cost exceeds the configured per-candidate budget

The gate design is adversarial. A candidate should not win by sounding supportive while becoming a worse tutor.

## Ranking

Rank only candidates that pass all gates.

Use component metrics first:

- MathTutorBench pedagogy score
- MathTutorBench student-understanding score
- TutorBench rubric pass rate at checkpoint
- private hidden eval score at final

If the demo needs one number, use:

```text
display_score =
  0.50 * MathTutorBench pedagogy score
+ 0.20 * MathTutorBench student-understanding score
+ 0.20 * TutorBench rubric pass rate
+ 0.10 * private hidden eval score
```

SafeTutors remains a gate, not a reward. Lower harm rate, cost, and latency are reported separately.

## Experiment Record

Every candidate run should store:

- candidate ID
- parent candidate IDs
- strategy spec
- response architecture
- prompts and few-shot examples
- generation action: seed, mutation, recombination, repair, or ablation
- research-agent rationale
- benchmark subset IDs
- raw tutor transcripts
- evaluator outputs
- component scores
- gate results
- accept/reject decision
- rejection reason, if any
- cost
- latency

## Demo Surface

The hackathon visual should show the research loop, not just a chatbot.

Required demo views:

- research-agent decision log
- candidate strategy graph or spec
- baseline versus candidate transcript
- score comparison by benchmark dimension
- hard-gate pass/fail panel
- experiment history table
- frontier of surviving candidates
- final winner versus baseline

The key visual story:

> The agent runs a three-hour research process, proposes stronger tutor strategies, learns from benchmark failures, rejects harmful shortcuts, and selects a winner that improves held-out tutor behavior.

## Success Criteria

The hackathon experiment succeeds if it can:

- evaluate a baseline tutor
- let a research agent choose the next search action
- evaluate candidate tutor strategy programs under a three-hour wall-clock budget
- reject unsafe or answer-leaking candidates
- select a valid winner
- show transcript-level evidence for the winner
- validate the winner against a private hidden eval
- clearly state that the result optimizes benchmarked tutor behavior, not proven learning outcomes

## Out of Scope

Do not include these in the hackathon methodology:

- model fine-tuning
- retrieval
- external tool use
- multimodal tutoring
- K-8-specific benchmarking
- model routing
- temperature optimization
- max-token optimization
- scoring-weight optimization
- editing the evaluator during the run
- optimizing directly for student satisfaction
- optimizing directly for generic helpfulness

## One-Line Plan

Run a three-hour autoresearch agent that searches over bounded tutor strategy programs, optimizes on MathTutorBench, gates with SafeTutors, validates with TutorBench, and final-checks the winner against a private hidden mini-eval.

## Sources

- Karpathy autoresearch: https://github.com/karpathy/autoresearch
- MathTutorBench: https://arxiv.org/abs/2502.18940
- TutorBench: https://scale.com/blog/tutorbench
- SafeTutors: https://arxiv.org/abs/2603.17373
- Generative Adversarial Nets: https://papers.nips.cc/paper/5423-generative-adversarial-nets
