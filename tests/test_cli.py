from autoresearch_tutor.cli import main


def test_real_openai_command_requires_confirm_flag() -> None:
    code = main(
        [
            "run-local-openai",
            "--inner-loop-tasks",
            "data/evals/smoke.jsonl",
            "--checkpoint-tasks",
            "data/evals/checkpoint.jsonl",
            "--final-tasks",
            "data/evals/final_private_template.jsonl",
        ]
    )

    assert code == 2
