from __future__ import annotations

import os
import shutil
from importlib.metadata import version

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()

    print("Dependency check:")
    for package in ("openai", "modal", "python-dotenv"):
        print(f"- {package}: {version(package)}")

    modal_path = shutil.which("modal")
    print(f"- modal CLI: {modal_path or 'not found on PATH'}")

    openai_key = os.getenv("OPENAI_API_KEY", "")
    secret_name = os.getenv("MODAL_OPENAI_SECRET_NAME", "openai-api-key")
    tutor_model = os.getenv("OPENAI_TUTOR_MODEL", "gpt-5.5")
    research_model = os.getenv("OPENAI_RESEARCH_MODEL", "gpt-5.5")
    judge_model = os.getenv("OPENAI_JUDGE_MODEL", "gpt-5.5")
    tutor_effort = os.getenv("OPENAI_TUTOR_REASONING_EFFORT", "medium")
    research_effort = os.getenv("OPENAI_RESEARCH_REASONING_EFFORT", "medium")
    judge_effort = os.getenv("OPENAI_JUDGE_REASONING_EFFORT", "medium")
    verbosity = os.getenv("OPENAI_TEXT_VERBOSITY", "medium")

    print("\nEnvironment check:")
    if openai_key:
        print("- OPENAI_API_KEY: set")
    else:
        print("- OPENAI_API_KEY: missing")

    print(f"- MODAL_OPENAI_SECRET_NAME: {secret_name}")
    print(f"- OPENAI_TUTOR_MODEL: {tutor_model} ({tutor_effort})")
    print(f"- OPENAI_RESEARCH_MODEL: {research_model} ({research_effort})")
    print(f"- OPENAI_JUDGE_MODEL: {judge_model} ({judge_effort})")
    print(f"- OPENAI_TEXT_VERBOSITY: {verbosity}")

    if not openai_key:
        print("\nNext step: copy .env.example to .env and set OPENAI_API_KEY.")
        return 1

    print("\nLocal setup looks ready. Modal login/secret status is checked by Modal CLI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
