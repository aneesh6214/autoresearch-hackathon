# Full Autoresearch Tutor Implementation Spec

## Objective

Build, run, and package an autoresearch system that optimizes an LLM-based tutoring strategy against tutoring-specific benchmarks, then provide an ephemeral local test UI for the optimized tutor and produce final reports.

This spec is the completion contract for the next implementation goal. Work should not stop until every acceptance criterion in this document is satisfied, blocked by an external dependency, or the explicit hard budgets are reached.

## Ground Rules

- The former reference codebase has been removed from the repository.
- CODESTYLE documents copied from the former reference codebase live in the main codebase.
- New code must follow the copied CODESTYLE guidance.
- The project is now tracked as a local git repository.
- Do not persist user-generated UI reports unless the user manually downloads them.
- The project may spend up to:
  - `$270` on OpenAI API.
  - `$270` on Modal.
- These are hard maximum budgets.
- The run may stop around 95% spend if continuing would risk exceeding the hard caps.

## Final Deliverables

The completed project must include:

1. A full autoresearch optimization system.
2. Downloaded/adapted public benchmark inputs.
3. A private hidden eval created locally and hidden from the research agent.
4. A completed autoresearch run with stored artifacts.
5. A frozen optimized tutor strategy or system of LLM calls.
6. A local ephemeral test UI modeled after the copied reference interaction pattern.
7. Three manually downloaded HTML reports from UI test runs.
8. One nicely formatted methodology HTML writeup.
9. All four HTML files placed in `reports/`.
10. Clear run instructions and artifact locations.

## Benchmark Stack

Download and adapt these benchmarks:

- MathTutorBench
- TutorBench
- SafeTutors

Optional diagnostics may be used if implementation time permits:

- MRBench / Unifying AI Tutor Evaluation
- BEA 2025 Shared Task

The first full run should use:

- MathTutorBench as the primary inner-loop tutoring-quality benchmark.
- SafeTutors as a hard safety/pedagogical-harm gate.
- TutorBench as checkpoint/generalization validation.
- A locally created private hidden eval as final validation.

## Benchmark Adaptation

All benchmark slices should be adapted into the project `EvalTask` JSONL format or an equivalent validated schema.

Each task must carry enough information for tutor generation and judge evaluation:

- task ID
- benchmark name
- split or phase
- subject
- student message or scenario
- target concept
- expected tutor behavior
- rubric
- answer-leakage risk
- metadata preserving source fields

Benchmark data should be separated by purpose:

- `inner_loop`: cheap recurring search signal.
- `checkpoint`: larger validation for top candidates.
- `final`: hidden or held-out validation only.

The research agent must never see the private hidden eval examples during search.

## Private Hidden Eval

Create a local private hidden eval of 30-50 examples.

It should cover:

- student asks for the direct answer
- student is confidently wrong
- arithmetic error
- conceptual error
- confused but not wrong
- incomplete work
- wrong formula
- right answer for wrong reason
- direct explanation is better than questioning
- Socratic questioning is useful
- over-explanation would hurt
- the tutor should ask the student to attempt the next step

The private eval should be stored separately from public benchmark slices and only used in final selection/validation.

## Optimized Artifact

The optimized artifact is a bounded tutor strategy program, not merely a single prompt.

Candidate strategies may vary:

- response architecture
- tutor policy prompts
- hidden planning step
- self-critique/revision step
- few-shot tutoring examples
- output structure
- answer-boundary rules
- scaffolding rules

Candidate strategies must not vary:

- benchmark examples
- evaluator prompts during a run
- scoring weights during a run
- safety gates during a run
- private hidden eval contents
- hardcoded benchmark answers
- model routing unless explicitly added as a bounded primitive
- external retrieval/tools unless added deliberately and reflected in the budget

## Tutor Style Target

The target style is primarily Socratic, but not rigidly Socratic.

The tutor should:

- diagnose student state and misconceptions
- ask targeted guiding questions when useful
- give hints before final answers
- preserve student agency
- avoid answer dumping
- provide direct explanations when pedagogically appropriate
- avoid vague or performative Socratic questioning
- keep cognitive load reasonable

The evaluator should decide whether a Socratic move, direct explanation, hint, or micro-step is most appropriate for the scenario.

## Models and Reasoning Effort

Use strong frontier OpenAI models by default:

- tutor model: `gpt-5.5`
- research agent model: `gpt-5.5`
- judge model: `gpt-5.5`

Recommended effort policy:

- Search-phase tutor calls: `medium`.
- Search-phase judge calls: `medium`.
- Research agent calls: `high` if candidate quality is weak or JSON reliability is poor; otherwise `medium`.
- Checkpoint/final judge calls: `high` or `xhigh` if runtime and budget allow.
- Final report/writeup generation: `medium` or `high`.

There is no separate API "fast mode" toggle assumed. Runtime should be controlled by batching, Modal parallelism, task-slice size, and phase-specific reasoning effort.

## Budget Policy

Track estimated and observed spend separately for:

- OpenAI tutor calls
- OpenAI research-agent calls
- OpenAI judge calls
- Modal compute

Hard caps:

- OpenAI API: `$270`
- Modal: `$270`

Stop or downgrade if:

- either budget reaches 95%
- projected next phase could exceed either hard cap
- checkpoint/final validation budget would be consumed by continued search

Prefer spending the budget on:

1. reliable benchmark evaluation
2. judge quality at checkpoint/final
3. candidate diversity
4. UI/report polish

Do not spend heavily on:

- evaluating candidates that already failed hard gates
- repeatedly testing the same failure mode
- oversized candidate prompts
- unnecessary long transcripts

## Stop Criteria

The autoresearch loop should stop when any of these occur:

1. OpenAI spend reaches 95% of `$270`.
2. Modal spend reaches 95% of `$270`.
3. Wall-clock optimization budget reaches 3 hours.
4. No checkpoint improvement occurs for 2 consecutive checkpoint rounds.
5. No candidate passes hard gates in 2 consecutive search rounds.
6. A candidate achieves clear improvement over baseline across checkpoint metrics and passes final/private validation.
7. The next planned phase cannot run without risking budget overrun.

The loop should preserve enough budget for:

- final private eval
- UI implementation/testing
- three UI test reports
- methodology writeup

## Autoresearch Loop

The loop should be controlled by a research agent.

Inputs to the research agent:

- current best strategy
- frontier of valid candidates
- rejected candidates
- failure modes
- evaluator summaries
- representative transcripts
- phase-level score table
- cost and latency
- remaining budget
- remaining time

Allowed research actions:

- generate candidate
- mutate candidate
- recombine candidates
- repair candidate
- ablate candidate component
- choose diagnostic public benchmark slice
- promote candidate to checkpoint
- stop and freeze winner

Forbidden research actions:

- inspect private hidden eval
- edit benchmarks
- edit evaluator prompts during the run
- edit gates during the run
- edit scoring weights during the run
- hardcode benchmark examples
- instruct tutor to satisfy judges rather than students

## Evaluation and Gates

Track component metrics, not only a single scalar:

- correctness
- pedagogy
- student understanding
- mistake identification
- mistake location
- hint quality
- actionability
- cognitive-load management
- tone
- answer leakage
- pedagogical harm rate
- hallucination/factuality risk
- inappropriate refusal
- cost
- latency

Hard gates:

- answer leakage materially increases over baseline
- SafeTutors harm rate materially increases over baseline
- correctness drops materially
- mistake identification drops below baseline
- mistake location drops below baseline
- hallucination/factuality risk increases
- response becomes too verbose/cognitively overloaded
- tutor refuses to explain when explanation is appropriate
- candidate exceeds per-candidate latency or cost budget

Ranking should occur only after gates pass.

## Run Artifacts

Every candidate run must store:

- candidate ID
- parent candidate IDs
- strategy spec
- response architecture
- prompts
- few-shot examples
- research-agent rationale
- generation action
- benchmark subset IDs
- transcripts
- judge outputs
- component scores
- gate results
- rejection reason
- cost estimate/observation
- latency

Every optimization run must store:

- run configuration
- benchmark slice manifests
- budget ledger
- phase summaries
- frontier history
- final winner
- final validation result
- known caveats

## UI Requirements

Build a local ephemeral web app modeled after the copied reference interaction pattern.

Required screens:

1. Pre-test/configuration window
   - include relevant tutor/run configuration if applicable
   - show selected optimized tutor strategy
   - show run metadata and benchmark summary

2. Chat interface
   - allow the user to chat with the optimized tutor
   - use the frozen winning strategy
   - preserve session state only in-browser/runtime
   - do not persist chats automatically

3. Report generation
   - provide a clear button to generate a report
   - report should be HTML
   - report should have clear formatting and colors
   - report content should reflect the tutoring session and autoresearch run
   - report should not persist unless manually downloaded by the user

The UI should preserve the reference interaction pattern, with different content/layout only where required by this project.

## UI Test Runs

Design and execute 3 test chats in the UI.

The three test chats should cover:

1. student asks for a direct answer
2. student makes a conceptual mistake
3. student has partial work or right answer for wrong reason

For each UI test run:

- complete the chat in the UI
- generate the HTML report
- manually download/save it into `reports/`
- name it clearly

Expected files:

- `reports/ui-test-1-direct-answer.html`
- `reports/ui-test-2-conceptual-mistake.html`
- `reports/ui-test-3-partial-work.html`

## Methodology Writeup

Create one additional HTML report:

- `reports/methodology.html`

The methodology report must be nicely formatted and include colors/clear sections.

It must have two clearly delimited parts:

1. Conceptual / High-Level Explanation
   - what autoresearch is
   - why tutor optimization is different from answer optimization
   - why safety gates matter
   - what the final tutor is meant to improve
   - what the experiment does not prove

2. Technical Details
   - benchmark stack
   - strategy search space
   - research-agent loop
   - evaluation/gating metrics
   - stop criteria
   - budget policy
   - final winner summary
   - caveats and limitations

## Reports Directory

At completion, `reports/` must contain exactly the expected deliverable HTML reports unless additional supporting files are clearly justified:

- `ui-test-1.html`
- `ui-test-2.html`
- `ui-test-3.html`
- `methodology.html`

If assets are needed, keep them local and organized under `reports/assets/`.

## Implementation Phases

### Phase 1: Code Style Capture

- Inspect the reference codebase only as needed before removal.
- Copy CODESTYLE documents out of the reference codebase into the main codebase.
- Summarize applicable style rules.
- Inspect the reference ephemeral UI shape.
- Remove the reference codebase before repository initialization.

### Phase 2: Benchmark Acquisition and Adaptation

- Download MathTutorBench.
- Download TutorBench.
- Download SafeTutors.
- Adapt benchmark records into project eval schema.
- Create public benchmark slices for inner-loop and checkpoint phases.
- Create the private hidden eval.
- Verify task counts and schema validity.

### Phase 3: Full Loop Hardening

- Add robust budget tracking.
- Add observed OpenAI usage tracking.
- Add run-phase manifests.
- Add resumable or inspectable run artifacts.
- Add Modal parallel candidate evaluation for search/checkpoint phases.
- Add stop-criteria enforcement.
- Add progress logs.

### Phase 4: Optimization Run

- Run smoke verification.
- Run full autoresearch loop.
- Monitor budget/time.
- Stop according to stop criteria.
- Freeze final winning tutor strategy.
- Validate winner against private hidden eval.

### Phase 5: UI

- Build local ephemeral test UI.
- Match the reference interaction pattern.
- Wire UI to the optimized tutor strategy.
- Add report generation/download.
- Ensure reports are not persisted unless manually downloaded.

### Phase 6: Report Generation

- Run three designed UI test sessions.
- Download/save their reports into `reports/`.
- Create `reports/methodology.html`.
- Verify all report files open and render correctly.

### Phase 7: Final Review

- Run tests.
- Run any local UI verification.
- Inspect final artifacts.
- Confirm budgets used.
- Confirm the reference codebase has been removed.
- Confirm deliverables exist.

## Acceptance Criteria

The work is complete only when:

- CODESTYLE documents are copied out of the former reference codebase.
- Main code follows the copied style guidance.
- Public benchmarks are downloaded/adapted.
- Private hidden eval exists and is not exposed to the research agent.
- Autoresearch loop runs to stop criteria.
- Winning tutor strategy is frozen and documented.
- Final validation results are stored.
- Local ephemeral UI works.
- UI uses the winning tutor strategy.
- UI can generate downloadable HTML reports.
- Three UI test reports are saved in `reports/`.
- Methodology HTML writeup is saved in `reports/`.
- Tests pass.
- Final response identifies key files, run artifacts, budget usage, and caveats.

## Known Risks

- Public benchmark formats may require custom adapters.
- TutorBench or SafeTutors may be expensive or slow if used too broadly.
- LLM-judge outputs can be noisy; checkpoint/final judging should use stronger effort if budget allows.
- A self-created private eval is useful but not as independent as a user-provided hidden set.
- Strong Socratic behavior can regress into vague questioning; evaluator should penalize that.
- Full local sequential runs are too slow; Modal parallelism is required for the real run.
