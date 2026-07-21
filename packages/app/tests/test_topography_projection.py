from datetime import UTC, datetime

from life_topography.application.project_topography import build_topography
from life_topography.domain.topography import EvidenceItem, NodeKind
from life_topography_sdk import EvidenceRecord


def email_evidence(
    identity: str,
    *,
    sender: tuple[str, str],
    recipients: list[tuple[str, str]],
    subject: str,
    day: int,
) -> EvidenceItem:
    return EvidenceItem(
        identity=identity,
        record=EvidenceRecord(
            source_record_id=identity,
            observed_at=datetime(2026, 6, day, tzinfo=UTC),
            content_type="application/vnd.life-topography.email-headers+json",
            payload={
                "kind": "email_headers",
                "message_id": f"{identity}@example.test",
                "sent_at": f"2026-06-{day:02d}T00:00:00+00:00",
                "date_valid": True,
                "subject": subject,
                "normalized_subject": subject.removeprefix("Re: ").casefold(),
                "sender": {"address": sender[0], "name": sender[1]},
                "recipients": [{"address": address, "name": name} for address, name in recipients],
            },
        ),
    )


def sample_evidence() -> list[EvidenceItem]:
    return [
        email_evidence(
            "evidence-1",
            sender=("ada@analytical.engine", "Ada Lovelace"),
            recipients=[("owner@example.net", "Z")],
            subject="Engine roadmap",
            day=1,
        ),
        email_evidence(
            "evidence-2",
            sender=("alias@example.net", "Z"),
            recipients=[
                ("ada@analytical.engine", "Ada"),
                ("grace@gmail.com", "Grace Hopper"),
            ],
            subject="Re: Engine roadmap",
            day=2,
        ),
    ]


def test_builds_people_organization_thread_and_weighted_edges() -> None:
    snapshot = build_topography(
        sample_evidence(), owner_addresses={"owner@example.net", "alias@example.net"}
    )

    labels = {(node.kind, node.label) for node in snapshot.nodes}
    assert (NodeKind.SELF, "You") in labels
    assert (NodeKind.PERSON, "Ada Lovelace") in labels
    assert (NodeKind.PERSON, "Grace Hopper") in labels
    assert (NodeKind.ORGANIZATION, "analytical.engine") in labels
    assert (NodeKind.ORGANIZATION, "gmail.com") not in labels
    assert (NodeKind.THREAD, "Engine roadmap") in labels

    ada = next(node for node in snapshot.nodes if node.label == "Ada Lovelace")
    interaction = next(
        edge
        for edge in snapshot.edges
        if edge.target_id == ada.id and edge.kind.value == "interacted_with"
    )
    assert interaction.weight == 2
    assert interaction.first_seen == datetime(2026, 6, 1, tzinfo=UTC)
    assert interaction.last_seen == datetime(2026, 6, 2, tzinfo=UTC)
    assert interaction.evidence_ids == ("evidence-1", "evidence-2")


def test_every_node_and_edge_has_provenance() -> None:
    snapshot = build_topography(
        sample_evidence(), owner_addresses={"owner@example.net", "alias@example.net"}
    )

    assert snapshot.nodes
    assert snapshot.edges
    assert all(item.evidence_ids for item in snapshot.nodes)
    assert all(item.evidence_ids for item in snapshot.edges)
    assert all(item.derivation == "email-header-projector@1" for item in snapshot.nodes)
    assert all(item.derivation == "email-header-projector@1" for item in snapshot.edges)


def test_projection_is_order_independent_and_rebuildable() -> None:
    evidence = sample_evidence()

    forward = build_topography(evidence, owner_addresses={"owner@example.net", "alias@example.net"})
    reverse = build_topography(
        list(reversed(evidence)),
        owner_addresses={"alias@example.net", "owner@example.net"},
    )
    empty = build_topography([], owner_addresses={"owner@example.net"})

    assert forward == reverse
    assert empty.nodes == ()
    assert empty.edges == ()


def test_display_name_choice_is_deterministic() -> None:
    evidence = sample_evidence()
    evidence.append(
        email_evidence(
            "evidence-3",
            sender=("ada@analytical.engine", "A. Lovelace"),
            recipients=[("owner@example.net", "Z")],
            subject="Other thread",
            day=3,
        )
    )

    snapshot = build_topography(evidence, owner_addresses={"owner@example.net"})
    ada = next(
        node
        for node in snapshot.nodes
        if node.kind is NodeKind.PERSON and node.detail == "ada@analytical.engine"
    )

    assert ada.label == "Ada Lovelace"
