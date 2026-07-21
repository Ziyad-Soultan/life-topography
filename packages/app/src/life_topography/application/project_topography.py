"""Deterministic projection from email-header evidence to a life map."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from life_topography.domain.topography import (
    EdgeKind,
    EvidenceItem,
    NodeKind,
    TopographyEdge,
    TopographyNode,
    TopographySnapshot,
)

_DERIVATION = "email-header-projector@1"
_REPLY_PREFIX = re.compile(r"^(?:(?:re|fw|fwd)\s*:\s*)+", re.IGNORECASE)
_PERSONAL_DOMAINS = frozenset(
    {
        "aol.com",
        "gmail.com",
        "googlemail.com",
        "hotmail.com",
        "icloud.com",
        "live.com",
        "me.com",
        "outlook.com",
        "proton.me",
        "protonmail.com",
        "yahoo.com",
    }
)


@dataclass
class _NodeAccumulator:
    kind: NodeKind
    key: str
    detail: str
    labels: Counter[str] = field(default_factory=Counter)
    evidence_ids: set[str] = field(default_factory=set)
    dates: set[datetime] = field(default_factory=set)


@dataclass
class _EdgeAccumulator:
    source_id: str
    target_id: str
    kind: EdgeKind
    evidence_ids: set[str] = field(default_factory=set)
    dates: set[datetime] = field(default_factory=set)


def build_topography(
    evidence: list[EvidenceItem], *, owner_addresses: set[str]
) -> TopographySnapshot:
    """Build a complete replaceable projection; input order cannot affect output."""

    owners = {_normalize_address(address) for address in owner_addresses}
    owners.discard("")
    nodes: dict[str, _NodeAccumulator] = {}
    edges: dict[str, _EdgeAccumulator] = {}

    for item in evidence:
        payload = _mapping(item.record.payload)
        if payload.get("kind") != "email_headers":
            continue
        participants = _email_participants(payload)
        if not participants:
            continue
        date = item.record.observed_at if payload.get("date_valid") is True else None
        self_id = _node_id(NodeKind.SELF, "self")
        _touch_node(nodes, self_id, NodeKind.SELF, "self", "", "You", item.identity, date)

        subject = _string(payload.get("subject"))
        normalized_subject = _string(payload.get("normalized_subject")) or "(no subject)"
        thread_id = _node_id(NodeKind.THREAD, normalized_subject)
        thread_label = _REPLY_PREFIX.sub("", subject).strip() or "(no subject)"
        _touch_node(
            nodes,
            thread_id,
            NodeKind.THREAD,
            normalized_subject,
            normalized_subject,
            thread_label,
            item.identity,
            date,
        )

        seen_addresses: set[str] = set()
        for address, name in participants:
            if address in seen_addresses:
                continue
            seen_addresses.add(address)
            if address in owners:
                participant_id = self_id
            else:
                participant_id = _node_id(NodeKind.PERSON, address)
                _touch_node(
                    nodes,
                    participant_id,
                    NodeKind.PERSON,
                    address,
                    address,
                    name or address,
                    item.identity,
                    date,
                )
                _touch_edge(
                    edges,
                    self_id,
                    participant_id,
                    EdgeKind.INTERACTED_WITH,
                    item.identity,
                    date,
                )
                domain = address.rsplit("@", 1)[1]
                if domain not in _PERSONAL_DOMAINS:
                    organization_id = _node_id(NodeKind.ORGANIZATION, domain)
                    _touch_node(
                        nodes,
                        organization_id,
                        NodeKind.ORGANIZATION,
                        domain,
                        domain,
                        domain,
                        item.identity,
                        date,
                    )
                    _touch_edge(
                        edges,
                        participant_id,
                        organization_id,
                        EdgeKind.MEMBER_OF,
                        item.identity,
                        date,
                    )
            _touch_edge(
                edges,
                participant_id,
                thread_id,
                EdgeKind.PARTICIPATED_IN,
                item.identity,
                date,
            )

    projected_nodes = tuple(
        sorted(
            (_project_node(node_id, value) for node_id, value in nodes.items()),
            key=lambda node: (node.kind.value, node.id),
        )
    )
    projected_edges = tuple(
        sorted(
            (_project_edge(edge_id, value) for edge_id, value in edges.items()),
            key=lambda edge: edge.id,
        )
    )
    return TopographySnapshot(nodes=projected_nodes, edges=projected_edges)


def _touch_node(
    nodes: dict[str, _NodeAccumulator],
    node_id: str,
    kind: NodeKind,
    key: str,
    detail: str,
    label: str,
    evidence_id: str,
    date: datetime | None,
) -> None:
    node = nodes.setdefault(node_id, _NodeAccumulator(kind=kind, key=key, detail=detail))
    node.labels[label] += 1
    node.evidence_ids.add(evidence_id)
    if date is not None:
        node.dates.add(date)


def _touch_edge(
    edges: dict[str, _EdgeAccumulator],
    source_id: str,
    target_id: str,
    kind: EdgeKind,
    evidence_id: str,
    date: datetime | None,
) -> None:
    edge_id = _edge_id(source_id, target_id, kind)
    edge = edges.setdefault(
        edge_id,
        _EdgeAccumulator(source_id=source_id, target_id=target_id, kind=kind),
    )
    edge.evidence_ids.add(evidence_id)
    if date is not None:
        edge.dates.add(date)


def _project_node(node_id: str, value: _NodeAccumulator) -> TopographyNode:
    label = sorted(
        value.labels,
        key=lambda candidate: (-value.labels[candidate], -len(candidate), candidate.casefold()),
    )[0]
    dates = sorted(value.dates)
    evidence_ids = tuple(sorted(value.evidence_ids))
    return TopographyNode(
        id=node_id,
        kind=value.kind,
        label=label,
        detail=value.detail,
        activity_count=len(evidence_ids),
        first_seen=dates[0] if dates else None,
        last_seen=dates[-1] if dates else None,
        evidence_ids=evidence_ids,
        derivation=_DERIVATION,
    )


def _project_edge(edge_id: str, value: _EdgeAccumulator) -> TopographyEdge:
    dates = sorted(value.dates)
    evidence_ids = tuple(sorted(value.evidence_ids))
    return TopographyEdge(
        id=edge_id,
        source_id=value.source_id,
        target_id=value.target_id,
        kind=value.kind,
        weight=len(evidence_ids),
        first_seen=dates[0] if dates else None,
        last_seen=dates[-1] if dates else None,
        evidence_ids=evidence_ids,
        derivation=_DERIVATION,
    )


def _email_participants(payload: dict[str, Any]) -> list[tuple[str, str]]:
    values: list[Any] = [payload.get("sender")]
    recipients = payload.get("recipients")
    if isinstance(recipients, list):
        values.extend(recipients)
    participants: list[tuple[str, str]] = []
    for value in values:
        participant = _mapping(value)
        address = _normalize_address(_string(participant.get("address")))
        if address:
            participants.append((address, _string(participant.get("name"))))
    return participants


def _mapping(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""


def _normalize_address(value: str) -> str:
    normalized = value.strip().casefold()
    return normalized if normalized.count("@") == 1 else ""


def _node_id(kind: NodeKind, key: str) -> str:
    digest = hashlib.sha256(f"{kind.value}:{key}".encode()).hexdigest()
    return f"{kind.value}:{digest}"


def _edge_id(source_id: str, target_id: str, kind: EdgeKind) -> str:
    digest = hashlib.sha256(f"{kind.value}:{source_id}:{target_id}".encode()).hexdigest()
    return f"{kind.value}:{digest}"
