from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from typing import Any

import job_orchestrator.agents as agents_module
from job_orchestrator.agents import AgentInvocationResult, DeepSeekAgentRegistry
from job_orchestrator.config import Settings
from job_orchestrator.schemas import AgentRole, Artifact, Claim, ProfileFact
from job_orchestrator.workflow import (
    _with_local_agent,
    build_graph,
    reviewer,
    synthetic_jobs,
    synthetic_profile,
)


def _state(*, use_model: bool = True) -> dict[str, Any]:
    return {
        "run_id": "run_model_test",
        "mode": "live",
        "auto_approve": True,
        "use_model": use_model,
        "query": "python automation",
        "profile": synthetic_profile().model_dump(mode="json"),
        "jobs": [job.model_dump(mode="json") for job in synthetic_jobs()],
        "approvals": [],
        "artifacts": [],
        "revision_count": 0,
        "agent_summaries": {},
        "agent_models": {},
    }


class SafeProposalRegistry:
    def __init__(self) -> None:
        self.roles: list[AgentRole] = []

    def invoke(
        self, role: AgentRole, payload: dict[str, Any]
    ) -> AgentInvocationResult:
        self.roles.append(role)
        if role == AgentRole.COORDINATOR:
            proposal: dict[str, Any] = {"summary": "Profile confirmation is ready."}
        elif role == AgentRole.SCOUT:
            proposal = {"summary": f"Reviewed {len(payload['jobs'])} bounded job records."}
        elif role == AgentRole.FIT_ANALYST:
            first_job_id = payload["ranked_summary"][0]["job_id"]
            proposal = {
                "mappings": [
                    {
                        "job_id": first_job_id,
                        "fact_ids": ["fact_sql"],
                        "gap_requirement_indices": [0],
                    }
                ]
            }
        elif role == AgentRole.TAILOR:
            first_job_id = payload["selected_jobs"][0]["job_id"]
            proposal = {
                "selections": [
                    {
                        "job_id": first_job_id,
                        "ordered_fact_ids": ["fact_sql", "fact_python"],
                    }
                ]
            }
        else:
            first_draft = payload["drafts"][0]
            proposal = {
                "observations": [
                    {
                        "artifact_id": first_draft["artifact_id"],
                        "claim_index": 0,
                        "code": "clarity",
                    }
                ]
            }
        return AgentInvocationResult(content=json.dumps(proposal), model="fake-local")


def test_model_proposals_influence_safe_fields_without_changing_scores() -> None:
    state = _state()
    baseline_state = copy.deepcopy(state)
    baseline_state["use_model"] = False
    baseline = build_graph().invoke(baseline_state)
    registry = SafeProposalRegistry()
    result = build_graph(agent_registry=registry).invoke(copy.deepcopy(state))

    baseline_scores = {
        item["job"]["job_id"]: item["score"] for item in baseline["ranked_jobs"]
    }
    model_scores = {
        item["job"]["job_id"]: item["score"] for item in result["ranked_jobs"]
    }
    assert model_scores == baseline_scores

    first_ranked = result["ranked_jobs"][0]
    assert any("fact_sql" in reason for reason in first_ranked["reasons"])
    assert any("Posting requirement flagged" in gap for gap in first_ranked["gaps"])

    first_artifact = result["artifacts"][0]
    assert [claim["fact_ids"] for claim in first_artifact["claims"]] == [
        ["fact_sql"],
        ["fact_python"],
    ]
    assert first_artifact["content"].index("Uses SQL") < first_artifact["content"].index(
        "Built Python"
    )
    assert result["review"]["approved"] is True
    assert result["review"]["issues"][0]["severity"] == "warning"
    assert result["agent_summaries"]["career_coordinator"] == (
        "Profile confirmation is ready."
    )
    assert result["agent_summaries"]["opportunity_scout"].startswith("Reviewed 3")
    assert set(registry.roles) == set(AgentRole)


class InvalidProposalRegistry:
    def invoke(
        self, role: AgentRole, payload: dict[str, Any]
    ) -> AgentInvocationResult:
        if role == AgentRole.COORDINATOR:
            proposal: dict[str, Any] = {"summary": "Ready."}
        elif role == AgentRole.SCOUT:
            proposal = {"summary": "Bounded results ready."}
        elif role == AgentRole.FIT_ANALYST:
            proposal = {
                "mappings": [
                    {
                        "job_id": payload["ranked_summary"][0]["job_id"],
                        "fact_ids": ["fact_not_offered"],
                        "gap_requirement_indices": [],
                    }
                ]
            }
        elif role == AgentRole.TAILOR:
            proposal = {
                "selections": [
                    {
                        "job_id": payload["selected_jobs"][0]["job_id"],
                        "ordered_fact_ids": ["fact_sql"],
                        "claim_text": "Invented a 900 percent revenue increase.",
                    }
                ]
            }
        else:
            proposal = {"observations": [], "approved": True}
        return AgentInvocationResult(content=json.dumps(proposal), model="fake-local")


def test_unknown_ids_and_free_form_claims_are_rejected_as_a_whole() -> None:
    state = _state()
    baseline_state = copy.deepcopy(state)
    baseline_state["use_model"] = False
    baseline = build_graph().invoke(baseline_state)
    result = build_graph(agent_registry=InvalidProposalRegistry()).invoke(
        copy.deepcopy(state)
    )

    assert [item["score"] for item in result["ranked_jobs"]] == [
        item["score"] for item in baseline["ranked_jobs"]
    ]
    assert result["ranked_jobs"][0]["reasons"] == baseline["ranked_jobs"][0]["reasons"]
    assert [claim["fact_ids"] for claim in result["artifacts"][0]["claims"]] == [
        ["fact_python"],
        ["fact_sql"],
    ]
    assert "900 percent" not in str(result["artifacts"])
    for role in ("fit_analyst", "application_tailor", "quality_reviewer"):
        assert "rejected" in result["agent_summaries"][role]


def test_existing_fact_is_rejected_when_it_was_not_in_the_bounded_offer() -> None:
    state = _state()
    profile = synthetic_profile()
    for index in range(18):
        profile.facts.append(
            ProfileFact(
                fact_id=f"fact_filler_{index}",
                category="skill",
                text=f"Verified bounded fact {index}.",
                verified=True,
            )
        )
    profile.facts.append(
        ProfileFact(
            fact_id="fact_verified_but_hidden",
            category="skill",
            text="This verified fact falls outside the twenty-item model payload.",
            verified=True,
        )
    )
    state["profile"] = profile.model_dump(mode="json")

    class HiddenFactRegistry(SafeProposalRegistry):
        def invoke(
            self, role: AgentRole, payload: dict[str, Any]
        ) -> AgentInvocationResult:
            if role == AgentRole.FIT_ANALYST:
                proposal = {
                    "mappings": [
                        {
                            "job_id": payload["ranked_summary"][0]["job_id"],
                            "fact_ids": ["fact_verified_but_hidden"],
                            "gap_requirement_indices": [],
                        }
                    ]
                }
                return AgentInvocationResult(
                    content=json.dumps(proposal), model="fake-local"
                )
            if role == AgentRole.TAILOR:
                return AgentInvocationResult(
                    content=json.dumps({"selections": []}), model="fake-local"
                )
            if role == AgentRole.REVIEWER:
                return AgentInvocationResult(
                    content=json.dumps({"observations": []}), model="fake-local"
                )
            return super().invoke(role, payload)

    result = build_graph(agent_registry=HiddenFactRegistry()).invoke(state)
    assert "rejected" in result["agent_summaries"]["fit_analyst"]
    assert "fact_verified_but_hidden" not in str(result["ranked_jobs"])


def test_model_cannot_approve_a_deterministically_false_claim() -> None:
    profile = synthetic_profile()
    false_artifact = Artifact(
        run_id="run_false_model",
        job_id="job_false",
        profile_id=profile.profile_id,
        kind="application_brief",
        title="False claim",
        content="Increased revenue by 900 percent.",
        claims=[
            Claim(
                text="Increased revenue by 900 percent.",
                fact_ids=["fact_python"],
            )
        ],
    )

    class EmptyReviewerRegistry:
        def invoke(
            self, _role: AgentRole, _payload: dict[str, Any]
        ) -> AgentInvocationResult:
            return AgentInvocationResult(
                content=json.dumps({"observations": []}), model="fake-local"
            )

    result = _with_local_agent(
        AgentRole.REVIEWER,
        reviewer,
        EmptyReviewerRegistry(),  # type: ignore[arg-type]
    )(
        {
            "use_model": True,
            "profile": profile.model_dump(mode="json"),
            "artifacts": [false_artifact.model_dump(mode="json")],
            "agent_summaries": {},
            "agent_models": {},
        }
    )
    assert result["review"]["approved"] is False
    assert result["review"]["issues"][0]["severity"] == "error"


def test_use_model_false_never_invokes_registry() -> None:
    class ExplodingRegistry:
        def invoke(self, _role: AgentRole, _payload: dict[str, Any]) -> None:
            raise AssertionError("registry must not be invoked")

    result = build_graph(agent_registry=ExplodingRegistry()).invoke(  # type: ignore[arg-type]
        _state(use_model=False)
    )
    assert result["stage"] == "completed"


def test_registry_neutralizes_remote_tracing_and_uses_empty_callbacks(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_OTEL_ENABLED", "true")
    calls: list[dict[str, Any]] = []
    prompts: list[str] = []

    class FakeChatAnthropic:
        def __init__(self, **_kwargs: Any) -> None:
            pass

    class FakeRunnable:
        def invoke(self, value: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
            calls.append({"value": value, "config": config})
            return {"messages": [SimpleNamespace(content='{"summary":"DeepSeek ready."}')]}

    def fake_create_agent(**kwargs: Any) -> FakeRunnable:
        prompts.append(kwargs["system_prompt"])
        return FakeRunnable()

    monkeypatch.setattr(agents_module, "ChatAnthropic", FakeChatAnthropic)
    monkeypatch.setattr(agents_module, "create_agent", fake_create_agent)
    credential_store = SimpleNamespace(get=lambda: "sk-test-value")
    registry = DeepSeekAgentRegistry(Settings(), credential_store)

    for name in (
        "LANGSMITH_TRACING",
        "LANGCHAIN_TRACING_V2",
        "LANGCHAIN_TRACING",
        "LANGSMITH_OTEL_ENABLED",
    ):
        assert agents_module.os.environ[name] == "false"

    result = registry.invoke(AgentRole.COORDINATOR, {"stage": "profile"})
    assert result.structured is not None
    assert calls[0]["config"] == {"callbacks": []}
    assert all("JSON Schema" in prompt for prompt in prompts)


def test_registry_extracts_json_from_anthropic_content_blocks(monkeypatch: Any) -> None:
    class FakeChatAnthropic:
        def __init__(self, **_kwargs: Any) -> None:
            pass

    class FakeRunnable:
        def invoke(self, _value: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
            assert config == {"callbacks": []}
            return {
                "messages": [
                    SimpleNamespace(
                        content=[
                            {"type": "thinking", "thinking": "private reasoning"},
                            {"type": "text", "text": '{"summary":"DeepSeek ready."}'},
                        ]
                    )
                ]
            }

    monkeypatch.setattr(agents_module, "ChatAnthropic", FakeChatAnthropic)
    monkeypatch.setattr(agents_module, "create_agent", lambda **_kwargs: FakeRunnable())
    registry = DeepSeekAgentRegistry(Settings(), SimpleNamespace(get=lambda: "sk-test-value"))

    result = registry.invoke(AgentRole.COORDINATOR, {"stage": "profile"})

    assert result.content == '{"summary":"DeepSeek ready."}'
    assert result.structured is not None
