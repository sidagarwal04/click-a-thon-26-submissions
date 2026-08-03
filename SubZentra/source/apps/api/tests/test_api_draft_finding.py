"""The Draft Finding surface of the authenticated API.

Split from `test_api.py` to keep both under the repository's 600-line limit.
The client harness and identity fixtures live there and are imported rather
than copied, so the two files cannot drift about what a request looks like.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from zentra_application_investigation import InvestigationNotFoundError
from zentra_domain_agent_execution import ConfidenceOutcome
from zentra_domain_investigation import (
    CitationFilter,
    CitationState,
    Claim,
    ClaimKind,
    Contradiction,
    DraftFinding,
    EvidenceCitation,
    RootCauseState,
)

from .test_api import (
    IdentityContext,
    InvestigationServiceStub,
    client,
    investigation_detail,
)


def structured_citation() -> EvidenceCitation:
    return EvidenceCitation(
        citation_id=UUID("cc000000-0000-0000-0000-000000000001"),
        tenant_id=UUID("20000000-0000-0000-0000-000000000002"),
        investigation_id=UUID("30000000-0000-0000-0000-000000000003"),
        metric="refund_amount",
        filters=(
            CitationFilter(member="Commerce.region", operator="equals", values=("EU",)),
        ),
        period="July 2026",
        grain="month",
        producing_execution_id=UUID("70000000-0000-0000-0000-000000000007"),
        aggregate_value="260.00",
        evaluator_outcome=ConfidenceOutcome(
            score=0.82, calibration_method="evaluator_independent_recheck"
        ),
        state=CitationState.ACTIVE,
    )


def structured_draft() -> DraftFinding:
    return DraftFinding(
        draft_finding_id=UUID("40000000-0000-0000-0000-000000000004"),
        tenant_id=UUID("20000000-0000-0000-0000-000000000002"),
        investigation_id=UUID("30000000-0000-0000-0000-000000000003"),
        version=2,
        created_at=datetime(2026, 7, 29, tzinfo=UTC),
        produced_by_execution_id=None,
        headline="EU refunds rose $240 in July.",
        summary="Governed EU refund amount rose from $20 to $260.",
        claims=(
            Claim(
                claim_id=UUID("50000000-0000-0000-0000-000000000001"),
                kind=ClaimKind.OBSERVED,
                text="EU refund amount rose from $20.00 to $260.00.",
                position=0,
                metric="refund_amount",
                value="260.00",
                period="July 2026",
                citation_ids=(UUID("cc000000-0000-0000-0000-000000000001"),),
            ),
            Claim(
                claim_id=UUID("50000000-0000-0000-0000-000000000002"),
                kind=ClaimKind.INTERPRETATION,
                text="The rise is concentrated in a single week.",
                position=1,
            ),
        ),
        contradictions=(Contradiction(detail="Recheck counted 8 rows, not 12."),),
        root_cause=RootCauseState.UNRESOLVED,
        confidence=ConfidenceOutcome(
            score=0.42, calibration_method="capped_sample_size"
        ),
    )


def authenticated(monkeypatch) -> None:
    async def resolve(*args: object, **kwargs: object) -> IdentityContext:
        return IdentityContext(
            user_id=UUID("10000000-0000-0000-0000-000000000001"),
            tenant_id=UUID("20000000-0000-0000-0000-000000000002"),
            email="owner@example.com",
            tenant_name="Acme Europe",
            role="owner",
        )

    monkeypatch.setattr("zentra_api.request_context.resolve_identity_context", resolve)


def test_a_legacy_investigation_is_not_dressed_up_as_a_structured_draft(
    monkeypatch,
) -> None:
    """The whole point of keeping the two side by side. An Investigation that
    ran before Insight has narrative and opaque pointers; reporting it as a
    Draft Finding would claim its sentences are individually citable when
    nothing can resolve them."""
    authenticated(monkeypatch)
    service = InvestigationServiceStub()
    with client(investigations=service) as test_client:
        response = test_client.get(
            "/v1/investigations/30000000-0000-0000-0000-000000000003",
            headers={"Authorization": "Bearer valid"},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["draft_finding"] is None
    # And the legacy shape is untouched — this is an additive change.
    assert body["finding"]["headline"] == "EU refunds rose $240 in July"
    assert body["finding"]["evidence_references"] == ["artifact://semantic/eu-refunds"]


def test_a_structured_draft_survives_the_api_round_trip(monkeypatch) -> None:
    """Claim order, the observed/interpretation split, the contradiction and
    the unresolved root cause all have to arrive as data — a client cannot
    re-derive any of them from prose."""
    authenticated(monkeypatch)
    service = InvestigationServiceStub()
    service.detail = investigation_detail(
        draft_finding=structured_draft(),
        evidence_citations=(structured_citation(),),
    )
    with client(investigations=service) as test_client:
        response = test_client.get(
            "/v1/investigations/30000000-0000-0000-0000-000000000003",
            headers={"Authorization": "Bearer valid"},
        )

    draft = response.json()["draft_finding"]
    assert response.status_code == 200
    assert draft["version"] == 2
    assert draft["root_cause"] == "unresolved"
    assert [claim["position"] for claim in draft["claims"]] == [0, 1]
    assert [claim["kind"] for claim in draft["claims"]] == [
        "observed",
        "interpretation",
    ]
    assert len(draft["claims"][0]["citation_ids"]) == 1
    assert draft["contradictions"] == [
        {"detail": "Recheck counted 8 rows, not 12.", "resolved": False}
    ]
    assert draft["confidence"] == {
        "kind": "confidence",
        "score": 0.42,
        "calibration_method": "capped_sample_size",
    }


def test_the_legacy_finding_is_still_served_beside_a_structured_draft(
    monkeypatch,
) -> None:
    """Additive means both, not either. Dropping `finding` the moment a draft
    exists would break every client written against Phase 1."""
    authenticated(monkeypatch)
    service = InvestigationServiceStub()
    service.detail = investigation_detail(
        draft_finding=structured_draft(),
        evidence_citations=(structured_citation(),),
    )
    with client(investigations=service) as test_client:
        response = test_client.get(
            "/v1/investigations/30000000-0000-0000-0000-000000000003",
            headers={"Authorization": "Bearer valid"},
        )

    body = response.json()
    assert body["finding"] is not None
    assert body["draft_finding"] is not None


def test_the_api_distinguishes_measurement_from_interpretation(monkeypatch) -> None:
    """Four concepts a reader must not have to infer from prose: what was
    measured, what an Agent made of it, what is still disputed, and whether the
    cause is known. Each arrives as its own field."""
    authenticated(monkeypatch)
    service = InvestigationServiceStub()
    service.detail = investigation_detail(
        draft_finding=structured_draft(),
        evidence_citations=(structured_citation(),),
    )
    with client(investigations=service) as test_client:
        response = test_client.get(
            "/v1/investigations/30000000-0000-0000-0000-000000000003",
            headers={"Authorization": "Bearer valid"},
        )

    draft = response.json()["draft_finding"]
    measured = next(c for c in draft["claims"] if c["kind"] == "observed")
    interpreted = next(c for c in draft["claims"] if c["kind"] == "interpretation")

    # Measured evidence arrives with the measurement, not just the label.
    assert measured["metric"] == "refund_amount"
    assert measured["value"] == "260.00"
    assert measured["period"] == "July 2026"

    # An interpretation carries none of its own — it is a reading of someone
    # else's measurement.
    assert interpreted["metric"] is None
    assert interpreted["value"] is None

    # Disputed, and unresolved causality, are separate fields again.
    assert draft["contradictions"][0]["resolved"] is False
    assert draft["root_cause"] == "unresolved"


def test_root_cause_unresolved_is_reported_even_on_a_confident_draft(
    monkeypatch,
) -> None:
    """The failure mode ADR 0011 exists to prevent: a high-confidence,
    fully-agreeing Investigation reading as though the cause were established."""
    authenticated(monkeypatch)
    service = InvestigationServiceStub()
    service.detail = investigation_detail(
        draft_finding=structured_draft(),
        evidence_citations=(structured_citation(),),
    )
    with client(investigations=service) as test_client:
        response = test_client.get(
            "/v1/investigations/30000000-0000-0000-0000-000000000003",
            headers={"Authorization": "Bearer valid"},
        )

    assert response.json()["draft_finding"]["root_cause"] == "unresolved"


def resolving(service: InvestigationServiceStub, result):
    """Point the stub's resolver at one outcome — a citation or an exception."""

    async def resolve(*args: object, **kwargs: object):
        if isinstance(result, Exception):
            raise result
        return result

    service.resolve_citation = resolve  # type: ignore[method-assign]
    return service


def test_an_authorized_reader_resolves_an_active_citation(monkeypatch) -> None:
    """Everything ADR 0011 says a citation identifies, in one response."""
    authenticated(monkeypatch)
    service = resolving(InvestigationServiceStub(), structured_citation())
    with client(investigations=service) as test_client:
        response = test_client.get(
            "/v1/investigations/30000000-0000-0000-0000-000000000003"
            "/citations/cc000000-0000-0000-0000-000000000001",
            headers={"Authorization": "Bearer valid"},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["state"] == "active"
    assert body["metric"] == "refund_amount"
    assert body["filters"] == [
        {"member": "Commerce.region", "operator": "equals", "values": ["EU"]}
    ]
    assert body["period"] == "July 2026"
    assert body["grain"] == "month"
    assert body["aggregate_value"] == "260.00"
    assert body["producing_execution_id"] == "70000000-0000-0000-0000-000000000007"
    assert body["evaluator_outcome"]["kind"] == "confidence"


def test_a_resolved_citation_carries_no_prohibited_payload(monkeypatch) -> None:
    """`extra="forbid"` makes this a property of the type, but the assertion is
    on the wire because that is where a future field would show up."""
    authenticated(monkeypatch)
    service = resolving(InvestigationServiceStub(), structured_citation())
    with client(investigations=service) as test_client:
        response = test_client.get(
            "/v1/investigations/30000000-0000-0000-0000-000000000003"
            "/citations/cc000000-0000-0000-0000-000000000001",
            headers={"Authorization": "Bearer valid"},
        )

    body = response.text.lower()
    for prohibited in ("rows", "prompt", "reasoning", "credential", "secret", "token"):
        assert prohibited not in body


def test_unexpectedly_missing_evidence_is_unavailable_not_a_tombstone(
    monkeypatch,
) -> None:
    """A fault and a Tenant's deliberate erasure are different facts. Reporting
    loss as a deletion would reassure a reader about data that is simply gone."""
    authenticated(monkeypatch)
    lost = replace(structured_citation(), state=CitationState.UNAVAILABLE)
    service = resolving(InvestigationServiceStub(), lost)
    with client(investigations=service) as test_client:
        response = test_client.get(
            "/v1/investigations/30000000-0000-0000-0000-000000000003"
            "/citations/cc000000-0000-0000-0000-000000000001",
            headers={"Authorization": "Bearer valid"},
        )

    assert response.status_code == 200
    assert response.json()["state"] == "unavailable"
    assert "tombstone" not in response.text.lower()


def test_another_tenants_citation_is_indistinguishable_from_nothing(
    monkeypatch,
) -> None:
    """A caller who could tell "not yours" from "does not exist" could confirm
    somebody else's evidence exists by copying an identifier."""
    authenticated(monkeypatch)
    service = resolving(
        InvestigationServiceStub(),
        InvestigationNotFoundError("Evidence was not found"),
    )
    with client(investigations=service) as test_client:
        foreign = test_client.get(
            "/v1/investigations/30000000-0000-0000-0000-000000000003"
            "/citations/cc000000-0000-0000-0000-000000000001",
            headers={"Authorization": "Bearer valid"},
        )
        unknown = test_client.get(
            "/v1/investigations/30000000-0000-0000-0000-000000000003"
            "/citations/99999999-9999-4999-8999-999999999999",
            headers={"Authorization": "Bearer valid"},
        )

    assert foreign.status_code == unknown.status_code == 404
    assert foreign.json() == unknown.json()
    # And the message says nothing about which case applied.
    assert foreign.json()["detail"] == "Evidence was not found"


def test_a_malformed_citation_id_discloses_nothing(monkeypatch) -> None:
    authenticated(monkeypatch)
    service = resolving(InvestigationServiceStub(), structured_citation())
    with client(investigations=service) as test_client:
        response = test_client.get(
            "/v1/investigations/30000000-0000-0000-0000-000000000003"
            "/citations/not-a-uuid",
            headers={"Authorization": "Bearer valid"},
        )

    assert response.status_code == 422
    assert "refund" not in response.text.lower()


def test_resolution_requires_authentication() -> None:
    service = resolving(InvestigationServiceStub(), structured_citation())
    with client(investigations=service) as test_client:
        response = test_client.get(
            "/v1/investigations/30000000-0000-0000-0000-000000000003"
            "/citations/cc000000-0000-0000-0000-000000000001",
        )

    assert response.status_code == 401


def test_the_caller_cannot_name_a_tenant(monkeypatch) -> None:
    """There is no Tenant parameter to override. Identity comes from the
    verified token, so a supplied one is simply ignored rather than trusted."""
    authenticated(monkeypatch)
    seen: list[object] = []

    async def resolve(actor, **kwargs: object):
        seen.append(actor.tenant_id)
        return structured_citation()

    service = InvestigationServiceStub()
    service.resolve_citation = resolve  # type: ignore[method-assign]
    with client(investigations=service) as test_client:
        response = test_client.get(
            "/v1/investigations/30000000-0000-0000-0000-000000000003"
            "/citations/cc000000-0000-0000-0000-000000000001"
            "?tenant_id=11111111-1111-4111-8111-111111111111",
            headers={"Authorization": "Bearer valid"},
        )

    assert response.status_code == 200
    assert seen == [UUID("20000000-0000-0000-0000-000000000002")]


def gated_detail(*failed: str):
    from zentra_application_investigation import PendingApproval

    detail = investigation_detail(draft_finding=structured_draft())
    return replace(
        detail,
        pending_approval=PendingApproval(
            approval_id=UUID("40000000-0000-0000-0000-000000000004"),
            reason="evidence_incomplete",
            requested_at=datetime(2026, 7, 29, tzinfo=UTC),
            can_decide=True,
            failed_conditions=failed,
        ),
    )


def test_the_api_reports_every_failed_publication_condition(monkeypatch) -> None:
    """A client shown only the headline would show a reviewer part of the
    picture. Both use the policy's own vocabulary."""
    authenticated(monkeypatch)
    service = InvestigationServiceStub()
    service.detail = gated_detail("converged", "confident", "evidenced")
    with client(investigations=service) as test_client:
        response = test_client.get(
            "/v1/investigations/30000000-0000-0000-0000-000000000003",
            headers={"Authorization": "Bearer valid"},
        )

    approval = response.json()["pending_approval"]
    assert approval["reason"] == "evidence_incomplete"
    assert approval["failed_conditions"] == ["converged", "confident", "evidenced"]


def test_an_automatically_published_investigation_reports_no_gate(
    monkeypatch,
) -> None:
    authenticated(monkeypatch)
    service = InvestigationServiceStub()
    with client(investigations=service) as test_client:
        response = test_client.get(
            "/v1/investigations/30000000-0000-0000-0000-000000000003",
            headers={"Authorization": "Bearer valid"},
        )

    assert response.json()["pending_approval"] is None


INVESTIGATION_UUID = "30000000-0000-0000-0000-000000000003"
DELETION_URL = f"/v1/investigations/{INVESTIGATION_UUID}/evidence-deletion"


def deleting(service: InvestigationServiceStub, result):
    async def delete_evidence(*args: object, **kwargs: object):
        if isinstance(result, Exception):
            raise result
        return result

    service.delete_evidence = delete_evidence  # type: ignore[method-assign]
    return service


def test_deletion_requires_naming_the_investigation_being_deleted(
    monkeypatch,
) -> None:
    """An irreversible action should be impossible to trigger by replaying a
    URL, and a confirmation the client can default to would not be one."""
    authenticated(monkeypatch)
    service = deleting(InvestigationServiceStub(), InvestigationServiceStub().detail)
    with client(investigations=service) as test_client:
        wrong = test_client.post(
            DELETION_URL,
            headers={"Authorization": "Bearer valid"},
            json={"confirm_investigation_id": "99999999-9999-4999-8999-999999999999"},
        )
        missing = test_client.post(
            DELETION_URL,
            headers={"Authorization": "Bearer valid"},
            json={},
        )

    assert wrong.status_code == 422
    assert missing.status_code == 422


def test_a_confirmed_deletion_returns_the_investigation(monkeypatch) -> None:
    authenticated(monkeypatch)
    service = deleting(InvestigationServiceStub(), InvestigationServiceStub().detail)
    with client(investigations=service) as test_client:
        response = test_client.post(
            DELETION_URL,
            headers={"Authorization": "Bearer valid"},
            json={"confirm_investigation_id": INVESTIGATION_UUID},
        )

    assert response.status_code == 200
    # Chronology survives: the timeline is still served after deletion.
    assert "timeline" in response.json()


def test_a_member_cannot_delete_evidence(monkeypatch) -> None:
    from zentra_application_investigation import PermissionDeniedError

    authenticated(monkeypatch)
    service = deleting(
        InvestigationServiceStub(),
        PermissionDeniedError("This membership cannot delete evidence"),
    )
    with client(investigations=service) as test_client:
        response = test_client.post(
            DELETION_URL,
            headers={"Authorization": "Bearer valid"},
            json={"confirm_investigation_id": INVESTIGATION_UUID},
        )

    assert response.status_code == 403


def test_deleting_a_live_investigation_is_a_conflict_not_a_refusal(
    monkeypatch,
) -> None:
    """ "Not yet" is a different answer from "not allowed", and a caller that
    conflated them would retry the wrong thing."""
    from zentra_application_investigation import ConflictError

    authenticated(monkeypatch)
    service = deleting(
        InvestigationServiceStub(),
        ConflictError(
            "Evidence can only be erased from a terminal Investigation; "
            "this one is running"
        ),
    )
    with client(investigations=service) as test_client:
        response = test_client.post(
            DELETION_URL,
            headers={"Authorization": "Bearer valid"},
            json={"confirm_investigation_id": INVESTIGATION_UUID},
        )

    assert response.status_code == 409
    assert "terminal" in response.json()["detail"]


def test_a_tombstone_response_carries_nothing_but_identity_and_time(
    monkeypatch,
) -> None:
    """`extra="forbid"` plus the absence of every other field is what stops a
    later change reintroducing the metric or the filters."""
    from datetime import UTC as _UTC

    from zentra_domain_investigation import Tombstone

    authenticated(monkeypatch)
    service = resolving(
        InvestigationServiceStub(),
        Tombstone(
            citation_id=UUID("cc000000-0000-0000-0000-000000000001"),
            category="tenant_request",
            erased_at=datetime(2026, 7, 31, 14, 0, tzinfo=_UTC),
        ),
    )
    with client(investigations=service) as test_client:
        response = test_client.get(
            f"/v1/investigations/{INVESTIGATION_UUID}"
            "/citations/cc000000-0000-0000-0000-000000000001",
            headers={"Authorization": "Bearer valid"},
        )

    body = response.json()
    assert response.status_code == 200
    assert set(body) == {"state", "citation_id", "category", "erased_at"}
    assert body["state"] == "tombstoned"
    text = response.text.lower()
    for erased in ("refund_amount", "260.00", "commerce.region", "july 2026"):
        assert erased not in text
