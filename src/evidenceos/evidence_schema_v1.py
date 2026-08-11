from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field

EpistemicStatus = Literal["verified","derived","ambiguous","conflicting","not_reported","unverified"]
EvidenceRole = Literal["randomized","allocated","analysed","completed","screened","unknown"]

class EvidencePointer(BaseModel):
    span_id: str
    quote: str
    start: int | None = None
    end: int | None = None

class VerifiedField(BaseModel):
    name: str
    value: Any = None
    unit: str | None = None
    status: EpistemicStatus = "unverified"
    confidence: float = Field(default=0.0, ge=0, le=1)
    provenance: list[EvidencePointer] = []
    derivation: str | None = None
    conflicts: list[Any] = []

class Arm(BaseModel):
    arm_id: str
    label: str
    n: VerifiedField | None = None
    intervention: VerifiedField | None = None

class SampleSet(BaseModel):
    role: EvidenceRole
    total_n: VerifiedField | None = None
    arms: list[Arm] = []

class ResultEstimate(BaseModel):
    result_id: str
    outcome: VerifiedField
    instrument: VerifiedField | None = None
    timepoint: VerifiedField | None = None
    intervention_arm: str | None = None
    comparator_arm: str | None = None
    n_intervention: VerifiedField | None = None
    n_comparator: VerifiedField | None = None
    group_values: dict[str, VerifiedField] = {}
    effect_measure: VerifiedField | None = None
    estimate: VerifiedField | None = None
    ci_lower: VerifiedField | None = None
    ci_upper: VerifiedField | None = None
    p_value: VerifiedField | None = None
    significance: VerifiedField | None = None
    direction: VerifiedField | None = None

class EvidenceAlarm(BaseModel):
    alarm_id: str
    severity: Literal["info","warning","critical"]
    code: str
    message: str
    related_fields: list[str] = []

class UniversalEvidenceRecord(BaseModel):
    schema_version: str = "1.0-alpha"
    report_id: str
    title: str
    study_design: VerifiedField | None = None
    trial_registration: VerifiedField | None = None
    sample_sets: list[SampleSet] = []
    results: list[ResultEstimate] = []
    alarms: list[EvidenceAlarm] = []
