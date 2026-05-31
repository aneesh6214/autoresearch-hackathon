# Autoresearch Tutor Runbook

## Current State

The full optimization loop has been implemented and run to completion. The canonical completed run is:

```text
runs/full-resume-20260530T230332Z
```

The selected tutor strategy is stored in:

```text
runs/full-resume-20260530T230332Z/winner_strategy.json
```

Implemented components:

- strategy schema for bounded tutor strategy programs
- baseline tutor strategy
- tutor strategy executor with four architectures
- LLM judge evaluator
- deterministic dry-run evaluator
- strategy constraint gate
- safety/regression gates
- research-agent candidate proposer
- runtime-based candidate budget helper
- successive-halving loop controller
- local CLI
- Modal remote candidate evaluator
- JSON artifact storage
- MathTutorBench, TutorBench sample, SafeTutors-style, and private hidden eval adapters
- local ephemeral UI API and React UI

## Safe Local Checks

These commands do not call OpenAI or run Modal jobs:

```bash
uv run python scripts/check_setup.py
uv run python -m autoresearch_tutor check
uv run pytest
```

Optional deterministic dry run:

```bash
uv run python -m autoresearch_tutor dry-run --output /tmp/autoresearch-tutor-dry-run
```

## Full Modal Run

This calls OpenAI and Modal. Use it only when intentionally starting a new optimization run:

```bash
uv run python -m autoresearch_tutor run-modal \
  --inner-loop-tasks data/evals/inner_loop_benchmark.jsonl \
  --checkpoint-tasks data/evals/checkpoint_benchmark.jsonl \
  --final-tasks data/private_hidden/final_private.jsonl \
  --output runs/full-$(date -u +%Y%m%dT%H%M%SZ) \
  --confirm-run
```

If a search run completes its inner loop but needs validation resumed, use:

```bash
uv run python -m autoresearch_tutor resume-modal-validation \
  --source-run runs/full-20260530T215706Z \
  --checkpoint-tasks data/evals/checkpoint_benchmark.jsonl \
  --final-tasks data/private_hidden/final_private.jsonl \
  --output runs/full-resume-$(date -u +%Y%m%dT%H%M%SZ) \
  --confirm-run
```

The legacy `data/evals/smoke.jsonl`, `data/evals/checkpoint.jsonl`, and
`data/evals/final_private_template.jsonl` files remain only for plumbing tests.

## Modal

Modal is wired at the remote candidate-evaluation level. The app import is safe and does not launch optimization:

```bash
uv run modal run src/autoresearch_tutor/modal_app.py
```

The remote function is:

```text
evaluate_candidate_remote
```

The Modal secret expected by default is:

```text
openai-api-key
```

Create or update it with:

```bash
uv run modal secret create openai-api-key --from-dotenv .env --force
```

## Important Guardrails

- The research agent can change tutor strategy programs.
- The research agent cannot change benchmark examples, judge prompts, scoring weights, or gates.
- Candidate strategies are rejected if they reference benchmark names, hidden evals, judge approval, or evaluator approval.
- The code currently supports at most two model calls per tutor response.
- No retrieval, external tools, model routing, or fine-tuning are implemented.
