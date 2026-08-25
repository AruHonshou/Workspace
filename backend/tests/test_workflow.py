from job_orchestrator.schemas import AgentRole, Artifact, Claim
from job_orchestrator.workflow import (
    build_graph,
    project_role_context,
    reviewer,
    synthetic_jobs,
    synthetic_profile,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command


def test_state_graph_runs_all_five_roles_offline() -> None:
    profile = synthetic_profile()
    jobs = synthetic_jobs()
    result = build_graph().invoke(
        {
            "run_id": "run_test",
            "mode": "replay",
            "auto_approve": True,
            "query": "python",
            "profile": profile.model_dump(mode="json"),
            "jobs": [job.model_dump(mode="json") for job in jobs],
            "approvals": [],
            "artifacts": [],
            "revision_count": 0,
        }
    )
    assert result["stage"] == "completed"
    assert result["review"]["approved"] is True
    assert len(result["approvals"]) == 3
    assert result["artifacts"]


def test_state_graph_pauses_at_human_gates() -> None:
    graph = build_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "human-gates"}}
    profile = synthetic_profile()
    first = graph.invoke(
        {
            "run_id": "run_gates",
            "mode": "replay",
            "auto_approve": False,
            "profile": profile.model_dump(mode="json"),
            "jobs": [job.model_dump(mode="json") for job in synthetic_jobs()],
            "approvals": [],
            "artifacts": [],
        },
        config,
    )
    assert first["__interrupt__"][0].value["kind"] == "profile_confirmation"
    second = graph.invoke(Command(resume={"decision": "approved"}), config)
    assert second["__interrupt__"][0].value["kind"] == "shortlist_selection"
    third = graph.invoke(Command(resume={"decision": "approved"}), config)
    assert third["__interrupt__"][0].value["kind"] == "application_approval"
    final = graph.invoke(Command(resume={"decision": "approved"}), config)
    assert final["stage"] == "completed"


def test_scout_role_projection_never_contains_profile_data() -> None:
    profile = synthetic_profile()
    state = {
        "query": "python",
        "profile": profile.model_dump(mode="json"),
        "jobs": [job.model_dump(mode="json") for job in synthetic_jobs()],
        "artifacts": [],
        "approvals": [],
    }
    projected = project_role_context(state, AgentRole.SCOUT)
    assert projected["query"] == "python"
    assert "profile" not in projected
    assert "verified_profile_facts" not in projected
    assert profile.name not in str(projected)


def test_reviewer_detects_false_wording_even_with_a_valid_fact_id() -> None:
    profile = synthetic_profile()
    fact = profile.facts[0]
    result = reviewer(
        {
            "profile": profile.model_dump(mode="json"),
            "artifacts": [
                Artifact(
                    run_id="run_false",
                    job_id="job_false",
                    profile_id=profile.profile_id,
                    kind="application_brief",
                    title="Seeded false claim",
                    content="Invented metric",
                    claims=[
                        Claim(
                            text="Increased revenue by 900 percent.",
                            fact_ids=[fact.fact_id],
                        )
                    ],
                ).model_dump(mode="json")
            ],
        }
    )
    assert result["review"]["approved"] is False
    assert result["review"]["issues"]
