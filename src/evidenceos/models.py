from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class Concept(BaseModel):
    label: str
    specified: bool
    concepts: list[str] = Field(default_factory=list)


class Comparator(BaseModel):
    label: str
    specified: bool
    types: list[str] = Field(default_factory=list)


class Outcome(BaseModel):
    outcome_id: str
    label: str


class TimeSpec(BaseModel):
    specified: bool
    label: str


class Ambiguity(BaseModel):
    field: str
    message: str
    severity: Literal["info", "warning", "material"]


class StructuredQuestion(BaseModel):
    question_id: str
    schema_version: Literal["0.1.0"] = "0.1.0"
    original_text: str
    normalized_text: str
    question_type: Literal["intervention_effectiveness", "unsupported"]
    framework: Literal["PICO", "none"]
    question_status: Literal[
        "well_specified", "partially_specified", "broad", "unsupported"
    ]
    population: Concept
    intervention: Concept
    comparator: Comparator
    outcomes: list[Outcome]
    time: TimeSpec
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    model_confidence: float = Field(ge=0, le=1)


class EvidenceUnit(BaseModel):
    evidence_unit_id: str
    question_id: str
    population: str
    intervention: str
    comparator: str
    outcome: str
    time: str


class ParseQuestionRequest(BaseModel):
    question: str = Field(min_length=3)


class ParseQuestionResponse(BaseModel):
    structured_question: StructuredQuestion
    evidence_units: list[EvidenceUnit]

class SearchStrategy(BaseModel):
    strategy_id: str
    question_id: str
    level: Literal["high_sensitivity", "balanced", "high_precision"]
    database: Literal["pubmed", "openalex"]
    query: str
    concepts_used: list[str] = Field(default_factory=list)
    generated_by: Literal["rules", "AI"] = "rules"


class CanonicalRecord(BaseModel):
    record_id: str
    title: str
    abstract: str | None = None
    year: int | None = None
    journal: str | None = None
    authors: list[str] = Field(default_factory=list)
    doi: str | None = None
    pmid: str | None = None
    openalex_id: str | None = None
    source_databases: list[str] = Field(default_factory=list)
    publication_types: list[str] = Field(default_factory=list)
    is_open_access: bool | None = None
    cited_by_count: int | None = None


class RetrievalSummary(BaseModel):
    question_id: str
    strategies: list[SearchStrategy]
    records_before_deduplication: int
    records_after_deduplication: int
    records: list[CanonicalRecord]


class RetrieveEvidenceRequest(BaseModel):
    question: str = Field(min_length=3)
    max_results_per_strategy: int = Field(default=50, ge=1, le=200)


class RetrieveEvidenceResponse(BaseModel):
    structured_question: StructuredQuestion
    evidence_units: list[EvidenceUnit]
    retrieval: RetrievalSummary

class DesignPrediction(BaseModel):
    final_label: Literal["systematic_review","meta_analysis","randomized_controlled_trial","nonrandomized_intervention","cohort","case_control","cross_sectional","qualitative","protocol","guideline","other","uncertain"]
    confidence: float = Field(ge=0, le=1)
    method: Literal["rules", "AI", "human", "hybrid"]
    rationale: str
    human_status: Literal["not_verified", "verified", "modified"] = "not_verified"

class EligibilityDimension(BaseModel):
    dimension: Literal["population", "intervention", "comparator", "outcome", "design"]
    judgement: Literal["match", "partial_match", "mismatch", "uncertain", "not_required"]
    rationale: str

class EligibilityPrediction(BaseModel):
    record_id: str
    overall: Literal["include", "exclude", "uncertain", "indirect"]
    confidence: float = Field(ge=0, le=1)
    dimensions: list[EligibilityDimension]
    method: Literal["rules", "AI", "hybrid"]
    exclusion_reason: str | None = None
    human_status: Literal["not_verified", "verified", "modified"] = "not_verified"

class StudyReportLink(BaseModel):
    study_id: str
    report_ids: list[str]
    link_confidence: float = Field(ge=0, le=1)
    link_method: Literal["deterministic", "heuristic", "AI", "human"]
    rationale: str

class StudyIntelligenceRecord(BaseModel):
    record: CanonicalRecord
    design: DesignPrediction
    eligibility: EligibilityPrediction

class RelevantStudySet(BaseModel):
    question_id: str
    records_evaluated: int
    likely_include: int
    indirect: int
    uncertain: int
    excluded: int
    study_intelligence: list[StudyIntelligenceRecord]
    study_links: list[StudyReportLink] = Field(default_factory=list)

class StudyIntelligenceRequest(BaseModel):
    question: StructuredQuestion
    records: list[CanonicalRecord]

class StudyIntelligenceResponse(BaseModel):
    relevant_study_set: RelevantStudySet

class SourceSpan(BaseModel):
    source_span_id: str
    report_id: str
    page: int | None = None
    section: str | None = None
    table: str | None = None
    paragraph: int | None = None
    text: str | None = None
    char_start: int | None = None
    char_end: int | None = None


class ExtractionField(BaseModel):
    extraction_id: str
    report_id: str
    field_name: str
    value: str | int | float | bool | None
    unit: str | None = None
    source_span_ids: list[str]
    extraction_method: Literal["rules", "AI", "human"]
    extraction_confidence: float = Field(ge=0, le=1)
    verification_status: Literal["not_verified", "verified", "modified"] = "not_verified"


class ArmDescription(BaseModel):
    arm_id: str
    label: str
    n: int | None = None
    description: str | None = None
    dose: str | None = None
    frequency: str | None = None
    duration: str | None = None
    supervision: str | None = None


class OutcomeResult(BaseModel):
    result_id: str
    report_id: str
    study_id: str | None = None
    outcome_name: str
    instrument: str | None = None
    timepoint: str | None = None
    intervention_arm: str | None = None
    comparator_arm: str | None = None
    n_intervention: int | None = None
    n_comparator: int | None = None
    effect_measure: str | None = None
    estimate: float | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None
    p_value: float | None = None
    direction: Literal[
        "favours_intervention",
        "favours_comparator",
        "no_clear_difference",
        "uncertain"
    ] = "uncertain"
    source_span_ids: list[str] = Field(default_factory=list)
    extraction_confidence: float = Field(ge=0, le=1)
    verification_status: Literal["not_verified", "verified", "modified"] = "not_verified"


class MethodologicalField(BaseModel):
    field_name: str
    value: str | bool | None
    source_span_ids: list[str]
    extraction_confidence: float = Field(ge=0, le=1)


class StructuredExtraction(BaseModel):
    report_id: str
    population_fields: list[ExtractionField] = Field(default_factory=list)
    intervention_arms: list[ArmDescription] = Field(default_factory=list)
    comparator_arms: list[ArmDescription] = Field(default_factory=list)
    outcomes: list[OutcomeResult] = Field(default_factory=list)
    methodological_fields: list[MethodologicalField] = Field(default_factory=list)
    source_spans: list[SourceSpan] = Field(default_factory=list)


class ExtractReportRequest(BaseModel):
    report_id: str
    title: str
    abstract: str | None = None
    full_text: str | None = None
    page_map: dict[str, str] | None = None


class ExtractReportResponse(BaseModel):
    extraction: StructuredExtraction

class RoB2Answer(BaseModel):
    question_id: str
    response: Literal["Y", "PY", "PN", "N", "NI", "NA"]
    rationale: str
    source_span_ids: list[str] = Field(default_factory=list)
    extraction_confidence: float = Field(ge=0, le=1)


class RoB2DomainAssessment(BaseModel):
    domain_id: Literal["D1", "D2", "D3", "D4", "D5"]
    domain_name: str
    signalling_answers: list[RoB2Answer]
    judgement: Literal["low", "some_concerns", "high", "unresolved"]
    rationale: str
    source_span_ids: list[str] = Field(default_factory=list)
    judgement_method: Literal["rules", "AI", "human", "hybrid"]
    verification_status: Literal["not_verified", "verified", "modified"] = "not_verified"


class RoB2Assessment(BaseModel):
    assessment_id: str
    report_id: str
    result_id: str | None = None
    effect_of_interest: Literal["assignment", "adhering"] = "assignment"
    domains: list[RoB2DomainAssessment]
    overall_judgement: Literal["low", "some_concerns", "high", "unresolved"]
    overall_rationale: str
    source_span_ids: list[str] = Field(default_factory=list)
    verification_status: Literal["not_verified", "verified", "modified"] = "not_verified"


class RoB2Request(BaseModel):
    extraction: StructuredExtraction
    result_id: str | None = None
    effect_of_interest: Literal["assignment", "adhering"] = "assignment"


class RoB2Response(BaseModel):
    assessment: RoB2Assessment

class CanonicalClaim(BaseModel):
    claim_id: str
    population: str
    intervention: str
    comparator: str
    outcome: str
    timepoint: str
    canonical_text: str
    result_ids: list[str] = Field(default_factory=list)


class BodyOfEvidence(BaseModel):
    body_id: str
    claim_id: str
    result_ids: list[str]
    unique_reports: int
    unique_studies: int
    total_participants: int | None = None
    compatible_effect_measure: str | None = None
    pooled_estimate: float | None = None
    pooled_ci_lower: float | None = None
    pooled_ci_upper: float | None = None
    effect_direction: Literal[
        "favours_intervention",
        "favours_comparator",
        "mixed",
        "no_clear_difference",
        "uncertain"
    ]
    heterogeneity_flag: Literal["low", "moderate", "high", "unknown"] = "unknown"


class GRADEDomainJudgement(BaseModel):
    domain: Literal[
        "risk_of_bias",
        "inconsistency",
        "indirectness",
        "imprecision",
        "publication_bias"
    ]
    judgement: Literal["not_serious", "serious", "very_serious", "unable_to_assess"]
    downgrade: int = Field(ge=0, le=2)
    rationale: str


class CertaintyAssessment(BaseModel):
    certainty_id: str
    body_id: str
    starting_level: Literal["high", "moderate", "low", "very_low"]
    domains: list[GRADEDomainJudgement]
    final_level: Literal["high", "moderate", "low", "very_low"]
    human_status: Literal["not_verified", "verified", "modified"] = "not_verified"


class CalibratedConclusion(BaseModel):
    conclusion_id: str
    claim_id: str
    certainty_id: str
    text: str
    epistemic_phrase: str
    certainty_level: Literal["high", "moderate", "low", "very_low"]


class EvidenceSynthesisRequest(BaseModel):
    question: StructuredQuestion
    results: list[OutcomeResult]
    rob2_assessments: list[RoB2Assessment] = Field(default_factory=list)


class EvidenceSynthesisResponse(BaseModel):
    claims: list[CanonicalClaim]
    bodies_of_evidence: list[BodyOfEvidence]
    certainty_assessments: list[CertaintyAssessment]
    conclusions: list[CalibratedConclusion]

class ChallengeDimensionResult(BaseModel):
    dimension: Literal[
        "contradictory_evidence",
        "active_comparator",
        "timepoint",
        "risk_of_bias_asymmetry",
        "higher_quality_evidence",
        "newer_evidence",
        "indirectness"
    ]
    triggered: bool
    severity: Literal["none", "minor", "material", "critical"]
    rationale: str
    related_result_ids: list[str] = Field(default_factory=list)
    related_assessment_ids: list[str] = Field(default_factory=list)


class ChallengeAssessment(BaseModel):
    challenge_id: str
    conclusion_id: str
    verdict: Literal[
        "survived",
        "survived_with_qualification",
        "materially_weakened",
        "rejected",
        "insufficient_evidence_to_challenge"
    ]
    dimensions: list[ChallengeDimensionResult]
    revised_conclusion: str | None = None
    rationale: str
    provenance_result_ids: list[str] = Field(default_factory=list)


class ChallengeRequest(BaseModel):
    conclusion: CalibratedConclusion
    claim: CanonicalClaim
    body: BodyOfEvidence
    all_results: list[OutcomeResult]
    rob2_assessments: list[RoB2Assessment] = Field(default_factory=list)
    all_claims: list[CanonicalClaim] = Field(default_factory=list)


class ChallengeResponse(BaseModel):
    assessment: ChallengeAssessment

class GapHypothesis(BaseModel):
    gap_hypothesis_id: str
    topic: str
    statement: str
    initial_gap_type: Literal[
        "quantity",
        "quality",
        "precision",
        "consistency",
        "population",
        "intervention",
        "comparator",
        "outcome",
        "temporal",
        "implementation",
        "experience",
        "replication",
        "construct",
        "unknown"
    ]
    status: Literal["hypothesized", "construct_checked", "challenged", "verified", "refined", "rejected", "unresolved"]
    detected_from: list[str] = Field(default_factory=list)


class ConstructCheck(BaseModel):
    construct_check_id: str
    gap_hypothesis_id: str
    input_term: str
    ambiguity: Literal["low", "moderate", "high"]
    candidate_constructs: list[str] = Field(default_factory=list)
    rationale: str


class GapEvidence(BaseModel):
    evidence_id: str
    gap_hypothesis_id: str
    source_type: Literal[
        "body_of_evidence",
        "claim",
        "challenge",
        "search_result",
        "systematic_review",
        "primary_study",
        "other"
    ]
    source_id: str
    supports_gap: bool
    directness: Literal["direct", "partial", "indirect"]
    rationale: str


class GapFalsificationAssessment(BaseModel):
    falsification_id: str
    gap_hypothesis_id: str
    verdict: Literal["verified", "refined", "rejected", "unresolved"]
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    final_gap_type: list[str] = Field(default_factory=list)
    confidence: Literal["low", "moderate", "high"]


class FinalGap(BaseModel):
    final_gap_id: str
    source_gap_hypothesis_id: str
    statement: str
    gap_types: list[str]
    confidence: Literal["low", "moderate", "high"]
    status: Literal["verified", "refined", "rejected", "unresolved"]
    verification_note: str


class ResearchOpportunity(BaseModel):
    opportunity_id: str
    final_gap_id: str
    suggested_design: Literal[
        "systematic_review",
        "randomized_trial",
        "cohort",
        "qualitative_study",
        "mixed_methods",
        "implementation_study",
        "methodological_study",
        "replication_study",
        "uncertain"
    ]
    proposed_question: str
    rationale: str
    caution: str


class GapEngineRequest(BaseModel):
    question: StructuredQuestion
    claims: list[CanonicalClaim]
    bodies_of_evidence: list[BodyOfEvidence]
    conclusions: list[CalibratedConclusion]
    challenges: list[ChallengeAssessment] = Field(default_factory=list)


class GapEngineResponse(BaseModel):
    hypotheses: list[GapHypothesis]
    construct_checks: list[ConstructCheck]
    gap_evidence: list[GapEvidence]
    falsifications: list[GapFalsificationAssessment]
    final_gaps: list[FinalGap]
    research_opportunities: list[ResearchOpportunity]

class AntiGapQuery(BaseModel):
    query_id: str
    gap_hypothesis_id: str
    database: Literal["pubmed", "openalex"]
    query: str
    target_constructs: list[str] = Field(default_factory=list)
    rationale: str


class ExternalGapEvidence(BaseModel):
    external_evidence_id: str
    gap_hypothesis_id: str
    record_id: str
    title: str
    database_sources: list[str]
    directness: Literal["direct", "partial", "indirect"]
    relation_to_gap: Literal["against_gap", "supports_gap", "uncertain"]
    rationale: str
    doi: str | None = None
    pmid: str | None = None
    year: int | None = None


class ExternalGapFalsificationResult(BaseModel):
    gap_hypothesis_id: str
    anti_gap_queries: list[AntiGapQuery]
    external_evidence: list[ExternalGapEvidence]
    external_verdict: Literal["reject", "refine", "strengthen", "unresolved"]
    rationale: str
    confidence: Literal["low", "moderate", "high"]


class ExternalGapFalsificationRequest(BaseModel):
    question: StructuredQuestion
    gap_hypothesis: GapHypothesis
    construct_check: ConstructCheck | None = None
    max_results_per_query: int = Field(default=25, ge=1, le=100)


class ExternalGapFalsificationResponse(BaseModel):
    result: ExternalGapFalsificationResult

