"""Model output contracts extract.v1 and visit.v1 (docs/14-data-mapping.md). Anything else fails validation."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Kind = Literal["medicine", "condition", "test", "appointment", "warning_sign", "restriction", "instruction", "result"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _non_empty(v: str) -> str:
    if not v.strip():
        raise ValueError("quote must not be empty")
    return v


class DocSource(Strict):
    page: int = Field(ge=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    quote: str

    _q = field_validator("quote")(_non_empty)


class DocumentMeta(Strict):
    doc_type: Literal["prescription", "lab_report", "discharge_summary", "specialist_letter", "imaging_report", "other"]
    doc_date: str | None = None
    issuer: str | None = None
    language: Literal["en", "hi", "mr", "mixed"]


class ExtractItem(Strict):
    kind: Kind
    title: str = Field(min_length=1)
    details: dict = Field(default_factory=dict)
    source: DocSource
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractAllergy(Strict):
    substance: str = Field(min_length=1)
    reaction: str | None = None
    severity: Literal["mild", "moderate", "severe", "unknown"] = "unknown"
    source: DocSource


class ExtractFollowUp(Strict):
    """The words only ("in two weeks"). Code computes the date (D-31)."""
    what: str = Field(min_length=1)
    due_text: str = Field(min_length=1)
    source: DocSource


class Provider(Strict):
    name: str = ""
    specialty: str = ""
    hospital: str = ""
    phone: str = ""


class Unreadable(Strict):
    page: int
    note: str


class ExtractV1(Strict):
    schema_version: Literal["extract.v1"]
    document: DocumentMeta
    items: list[ExtractItem] = Field(default_factory=list)
    allergy_statement: Literal["listed", "none_stated", "not_mentioned"]
    allergies: list[ExtractAllergy] = Field(default_factory=list)
    providers: list[Provider] = Field(default_factory=list)
    unreadable: list[Unreadable] = Field(default_factory=list)
    follow_ups: list[ExtractFollowUp] = Field(default_factory=list)


class SpeakerRole(Strict):
    label: str = Field(min_length=1, max_length=4)
    role: Literal["doctor", "patient", "family", "nurse", "other", "unknown"]
    name: str | None = None


class VisitSource(Strict):
    segment_ids: list[str] = Field(min_length=1)
    quote: str

    _q = field_validator("quote")(_non_empty)


class VisitItem(Strict):
    kind: Literal["medicine", "test", "appointment", "warning_sign", "restriction", "instruction", "condition"]
    change: Literal["new", "changed", "stopped", "unchanged_mention"]
    title: str = Field(min_length=1)
    details: dict = Field(default_factory=dict)
    source: VisitSource
    confidence: float = Field(ge=0.0, le=1.0)


class VisitAllergy(Strict):
    substance: str = Field(min_length=1)
    reaction: str | None = None
    stated_by: Literal["doctor", "patient", "family"]
    source: VisitSource


class VisitFollowUp(Strict):
    what: str = Field(min_length=1)
    due_text: str = Field(min_length=1)
    source: VisitSource


class VisitUnclear(Strict):
    segment_ids: list[str]
    note: str


class VisitV1(Strict):
    schema_version: Literal["visit.v1"]
    speaker_roles: list[SpeakerRole] = Field(default_factory=list)
    items: list[VisitItem] = Field(default_factory=list)
    allergies_mentioned: list[VisitAllergy] = Field(default_factory=list)
    unclear: list[VisitUnclear] = Field(default_factory=list)
    follow_ups: list[VisitFollowUp] = Field(default_factory=list)
