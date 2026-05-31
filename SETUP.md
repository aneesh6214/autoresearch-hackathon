# Setup

## Install Dependencies

```bash
uv sync
```

## OpenAI Key

Copy the example env file:

```bash
cp .env.example .env
```

Then edit `.env` and set:

```bash
OPENAI_API_KEY=your_openai_key_here
```

The default model is `gpt-5.5` with medium reasoning effort:

```bash
OPENAI_TUTOR_MODEL=gpt-5.5
OPENAI_RESEARCH_MODEL=gpt-5.5
OPENAI_JUDGE_MODEL=gpt-5.5
OPENAI_TUTOR_REASONING_EFFORT=medium
OPENAI_RESEARCH_REASONING_EFFORT=medium
OPENAI_JUDGE_REASONING_EFFORT=medium
OPENAI_TEXT_VERBOSITY=medium
OPENAI_MAX_OUTPUT_TOKENS=8192
```

There is no separate API "fast mode" toggle. If runtime is too slow, reduce reasoning effort for search-phase candidates after measuring candidate throughput. If quality is too weak, raise research or judge effort to `high` or `xhigh` for checkpoint/final phases.

## Modal Login

After dependencies are installed, authenticate Modal:

```bash
uv run modal setup
```

If Modal gives you a token pair instead, use the command it prints.

## Modal Secret for OpenAI

Create a Modal secret so remote Modal workers can call OpenAI:

```bash
uv run modal secret create openai-api-key --from-dotenv .env
```

The secret name should match `MODAL_OPENAI_SECRET_NAME` in `.env`.

To update the secret later:

```bash
uv run modal secret create openai-api-key --from-dotenv .env --force
```

## Verify Local Setup

```bash
uv run python scripts/check_setup.py
```
