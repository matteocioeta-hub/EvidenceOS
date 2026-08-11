from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ProjectQuestion(BaseModel):
    question: str = ""
    population: str = ""
    intervention: str = ""
    comparator: str = ""
    outcomes: str = ""
    timepoint: str = ""


class ProjectEvent(BaseModel):
    event_id: str
    event_type: str
    timestamp: str
    label: str
    payload: dict[str, Any] = Field(default_factory=dict)


class EvidenceOSProject(BaseModel):
    schema_version: str = "11.0-alpha"
    project_id: str
    name: str = Field(min_length=1, max_length=200)
    created_at: str
    updated_at: str
    question: ProjectQuestion = Field(default_factory=ProjectQuestion)
    corpus: list[dict[str, Any]] = Field(default_factory=list)
    latest_synthesis: dict[str, Any] | None = None
    synthesis_history: list[dict[str, Any]] = Field(default_factory=list)
    events: list[ProjectEvent] = Field(default_factory=list)


class ProjectValidationRequest(BaseModel):
    project: dict[str, Any]


class ProjectValidationResponse(BaseModel):
    valid: bool
    project: EvidenceOSProject
    warnings: list[str] = Field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_project(request: ProjectValidationRequest) -> ProjectValidationResponse:
    project = EvidenceOSProject.model_validate(request.project)

    warnings: list[str] = []
    if project.schema_version != "11.0-alpha":
        warnings.append(
            f"Imported schema version is {project.schema_version}; EvidenceOS v11 expects 11.0-alpha."
        )

    # Defensive limits for browser-based alpha persistence.
    if len(project.corpus) > 500:
        raise ValueError("A project cannot contain more than 500 stored studies in the v11 alpha.")
    if len(project.events) > 2000:
        raise ValueError("A project cannot contain more than 2000 history events in the v11 alpha.")
    if len(project.synthesis_history) > 250:
        raise ValueError("A project cannot contain more than 250 synthesis snapshots in the v11 alpha.")

    # Imported projects receive a fresh updated timestamp but retain provenance.
    project.updated_at = _now()

    return ProjectValidationResponse(valid=True, project=project, warnings=warnings)
