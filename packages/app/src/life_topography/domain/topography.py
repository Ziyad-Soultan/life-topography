"""Canonical, evidence-backed topography projection models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from life_topography_sdk import EvidenceRecord
from pydantic import BaseModel, ConfigDict


class NodeKind(StrEnum):
    SELF = "self"
    PERSON = "person"
    ORGANIZATION = "organization"
    THREAD = "thread"


class EdgeKind(StrEnum):
    INTERACTED_WITH = "interacted_with"
    MEMBER_OF = "member_of"
    PARTICIPATED_IN = "participated_in"


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    identity: str
    record: EvidenceRecord


class TopographyNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    kind: NodeKind
    label: str
    detail: str
    activity_count: int
    first_seen: datetime | None
    last_seen: datetime | None
    evidence_ids: tuple[str, ...]
    derivation: str


class TopographyEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    source_id: str
    target_id: str
    kind: EdgeKind
    weight: int
    first_seen: datetime | None
    last_seen: datetime | None
    evidence_ids: tuple[str, ...]
    derivation: str


class TopographySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    nodes: tuple[TopographyNode, ...]
    edges: tuple[TopographyEdge, ...]
