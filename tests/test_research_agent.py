from autoresearch_tutor.research_agent import SeededResearchAgent, parse_research_candidate
from autoresearch_tutor.schema import GenerationAction, ResponseArchitecture


def test_seeded_agent_can_generate_requested_batch_size() -> None:
    decisions = SeededResearchAgent().propose(frontier=[], history=[], count=7)

    assert len(decisions) == 7
    assert all(decision.strategy is not None for decision in decisions)
    assert {
        decision.strategy.response_architecture for decision in decisions if decision.strategy
    } >= {
        ResponseArchitecture.SINGLE_PASS,
        ResponseArchitecture.PLAN_THEN_ANSWER,
        ResponseArchitecture.SELF_CRITIQUE_REVISE,
        ResponseArchitecture.DIAGNOSE_THEN_TUTOR,
    }


def test_parse_research_candidate_repairs_architecture_in_action_field() -> None:
    decision = parse_research_candidate(
        {
            "action": "self_critique_revise",
            "strategy": {
                "tutor_policy": "Draft, critique, and revise the tutoring response.",
            },
        }
    )

    assert decision.strategy is not None
    assert decision.strategy.generation_action == GenerationAction.MUTATION
    assert decision.strategy.response_architecture == ResponseArchitecture.SELF_CRITIQUE_REVISE
