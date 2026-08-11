from __future__ import annotations

import re
from pydantic import BaseModel, Field

from .extraction_engine import ExtractionEngine
from .rob2_engine import RoB2Engine


class AppraisalDomain(BaseModel):
    domain: str
    judgement: str
    rationale: str


class UniversalTrustAssessment(BaseModel):
    design: str
    framework: str
    status: str
    headline: str
    explanation: str
    overall_judgement: str
    domains: list[AppraisalDomain] = Field(default_factory=list)
    outcome_assessments: list[dict] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def _has(text: str, *patterns: str) -> bool:
    return any(re.search(p, text, flags=re.I | re.S) for p in patterns)


def detect_design(title: str, text: str) -> str:
    blob = f"{title}\n{text[:30000]}"

    if _has(blob, r"\bmeta-analysis\b", r"\bmeta analysis\b"):
        return "meta_analysis"
    if _has(blob, r"\bsystematic review\b"):
        return "systematic_review"
    if _has(blob, r"\bdiagnostic accuracy\b", r"\bsensitivity\b.{0,80}\bspecificity\b", r"\bindex test\b"):
        return "diagnostic_accuracy"
    if _has(blob, r"\bqualitative\b", r"\bthematic analysis\b", r"\bphenomenolog"):
        return "qualitative"
    if _has(blob, r"\brandomi[sz](?:ed|ation|ation)\b", r"\brandomly assigned\b"):
        return "randomized_controlled_trial"
    if _has(blob, r"\bcase[- ]control\b"):
        return "case_control"
    if _has(blob, r"\bcross[- ]sectional\b"):
        return "cross_sectional"
    if _has(blob, r"\bcohort\b", r"\bprospective observational\b", r"\bretrospective observational\b"):
        return "cohort"
    if _has(blob, r"\bprotocol\b"):
        return "protocol"
    if _has(blob, r"\bguideline\b", r"\bclinical practice guideline\b"):
        return "guideline"
    if _has(blob, r"\bnon[- ]randomi[sz]ed\b", r"\bquasi[- ]experimental\b", r"\bcontrolled before[- ]after\b"):
        return "nonrandomized_intervention"
    return "other"


def _domain(name: str, condition: bool | None, yes: str, no: str) -> AppraisalDomain:
    if condition is True:
        return AppraisalDomain(domain=name, judgement="signal_present", rationale=yes)
    if condition is False:
        return AppraisalDomain(domain=name, judgement="not_verified", rationale=no)
    return AppraisalDomain(domain=name, judgement="unresolved", rationale=no)


def _generic_observational(text: str, design: str) -> UniversalTrustAssessment:
    confounding = _has(text, r"\bconfound", r"\badjusted for\b", r"\bmultivariable\b", r"\bpropensity")
    selection = _has(text, r"\binclusion criteria\b", r"\bexclusion criteria\b", r"\beligib")
    missing = _has(text, r"\bmissing data\b", r"\blost to follow", r"\bmultiple imputation\b")
    measurement = _has(text, r"\bvalidated\b", r"\breliab", r"\bblinded assessor\b")
    prereg = _has(text, r"\bpre[- ]register", r"\bregistered protocol\b", r"\bstatistical analysis plan\b")

    domains = [
        _domain("Selection of participants", selection,
                "Eligibility/selection information was detected.",
                "Selection procedures require full human verification."),
        _domain("Confounding", confounding,
                "Adjustment/confounding information was detected.",
                "Important confounders and adequacy of adjustment remain unresolved."),
        _domain("Measurement", measurement,
                "A measurement-quality signal was detected.",
                "Measurement validity and differential measurement remain unresolved."),
        _domain("Missing data", missing,
                "Missing-data handling was mentioned.",
                "Missingness amount, mechanism and handling require verification."),
        _domain("Selective reporting", prereg,
                "A preregistration/protocol signal was detected.",
                "Prespecification and selective reporting cannot be established automatically."),
    ]

    return UniversalTrustAssessment(
        design=design,
        framework="Design-specific observational appraisal",
        status="preliminary_full_text_assistance",
        headline="Preliminary methodological appraisal available",
        explanation=(
            "EvidenceOS detected methodological signals in the full text. "
            "This is structured decision support, not a validated final risk-of-bias judgement."
        ),
        overall_judgement="human_verification_required",
        domains=domains,
        limitations=[
            "No single generic observational score is treated as a substitute for design-specific judgement.",
            "Clinical/domain knowledge may be required to identify important confounders.",
        ],
    )


def _systematic_review(text: str, design: str) -> UniversalTrustAssessment:
    protocol = _has(text, r"\bprospero\b", r"\bprotocol\b.{0,60}\bregistered\b")
    databases = _has(text, r"\bpubmed\b", r"\bmedline\b", r"\bembase\b", r"\bcinahl\b")
    dual = _has(text, r"\btwo reviewers\b", r"\bindependently\b.{0,50}\breviewer")
    rob = _has(text, r"\brisk of bias\b", r"\brob 2\b", r"\brobins[- ]i\b")
    pubbias = _has(text, r"\bfunnel plot\b", r"\bpublication bias\b", r"\begger")

    domains = [
        _domain("Prospective protocol", protocol, "Protocol/registration signal detected.", "Protocol registration not verified."),
        _domain("Comprehensive search", databases, "Multiple bibliographic database signals detected.", "Search comprehensiveness requires verification."),
        _domain("Duplicate review processes", dual, "Independent/duplicate reviewer process detected.", "Duplicate selection/extraction not verified."),
        _domain("Risk-of-bias assessment", rob, "Risk-of-bias methods detected.", "Risk-of-bias methods not verified."),
        _domain("Publication bias", pubbias, "Publication-bias assessment signal detected.", "Publication-bias assessment not verified."),
    ]
    return UniversalTrustAssessment(
        design=design,
        framework="AMSTAR 2-oriented appraisal",
        status="preliminary_full_text_assistance",
        headline="Preliminary review-methods appraisal available",
        explanation=(
            "EvidenceOS maps detectable full-text signals to major systematic-review appraisal domains. "
            "It does not claim a final AMSTAR 2 rating without human verification of all items."
        ),
        overall_judgement="human_verification_required",
        domains=domains,
    )


def _diagnostic(text: str) -> UniversalTrustAssessment:
    sampling = _has(text, r"\bconsecutive\b", r"\brandom sample\b")
    index_blind = _has(text, r"\bindex test\b.{0,100}\bblind", r"\bblinded\b.{0,80}\bindex test\b")
    refstandard = _has(text, r"\breference standard\b")
    flow = _has(text, r"\bflow and timing\b", r"\ball patients\b.{0,80}\breference standard\b")

    domains = [
        _domain("Patient selection", sampling, "Consecutive/random sampling signal detected.", "Patient-selection bias requires verification."),
        _domain("Index test", index_blind, "Blinding/interpretation signal for index test detected.", "Index-test interpretation bias remains unresolved."),
        _domain("Reference standard", refstandard, "Reference standard explicitly identified.", "Reference-standard validity requires verification."),
        _domain("Flow and timing", flow, "Flow/timing signal detected.", "Flow, timing and verification bias remain unresolved."),
    ]
    return UniversalTrustAssessment(
        design="diagnostic_accuracy",
        framework="QUADAS-2-oriented appraisal",
        status="preliminary_full_text_assistance",
        headline="Preliminary diagnostic-accuracy appraisal available",
        explanation=(
            "EvidenceOS structures full-text signals around diagnostic-accuracy bias domains. "
            "Final QUADAS-2 judgements require reviewer verification."
        ),
        overall_judgement="human_verification_required",
        domains=domains,
    )


def _qualitative(text: str) -> UniversalTrustAssessment:
    sampling = _has(text, r"\bpurposive\b", r"\bpurposeful\b", r"\bmaximum variation\b")
    reflexivity = _has(text, r"\breflexiv", r"\bresearcher positioning\b")
    analysis = _has(text, r"\bthematic analysis\b", r"\bframework analysis\b", r"\bgrounded theory\b")
    quotes = _has(text, r"\bparticipant quote", r"\bverbatim quote", r"\bquotation")
    ethics = _has(text, r"\bethics approval\b", r"\bethical approval\b", r"\binformed consent\b")

    domains = [
        _domain("Sampling strategy", sampling, "Qualitative sampling strategy detected.", "Sampling appropriateness requires verification."),
        _domain("Reflexivity", reflexivity, "Reflexivity signal detected.", "Researcher reflexivity/relationship not verified."),
        _domain("Analytic approach", analysis, "Named qualitative analytic approach detected.", "Analytic rigor requires verification."),
        _domain("Data-to-finding grounding", quotes, "Participant-quotation signal detected.", "Grounding of findings in data requires verification."),
        _domain("Ethics", ethics, "Ethics/consent signal detected.", "Ethical procedures not verified."),
    ]
    return UniversalTrustAssessment(
        design="qualitative",
        framework="CASP/JBI-oriented qualitative appraisal",
        status="preliminary_full_text_assistance",
        headline="Preliminary qualitative appraisal available",
        explanation=(
            "EvidenceOS identifies reporting and methodological signals relevant to qualitative appraisal. "
            "Interpretive quality and reflexivity require human qualitative-methods judgement."
        ),
        overall_judgement="human_verification_required",
        domains=domains,
    )


def _rct(report_id: str, title: str, text: str) -> UniversalTrustAssessment:
    extraction = ExtractionEngine().extract(report_id, title, text)
    engine = RoB2Engine()
    assessments = []

    targets = extraction.outcomes or [None]
    for result in targets:
        rid = result.result_id if result is not None else None
        rob = engine.assess(extraction, result_id=rid)
        assessments.append({
            "result_id": rid,
            "outcome": result.outcome_name if result is not None else "Outcome not deterministically mapped",
            "timepoint": result.timepoint if result is not None else None,
            "effect_measure": result.effect_measure if result is not None else None,
            "overall_judgement": rob.overall_judgement,
            "overall_rationale": rob.overall_rationale,
            "domains": [
                {
                    "domain_id": d.domain_id,
                    "domain_name": d.domain_name,
                    "judgement": d.judgement,
                    "rationale": d.rationale,
                }
                for d in rob.domains
            ],
        })

    return UniversalTrustAssessment(
        design="randomized_controlled_trial",
        framework="RoB 2",
        status="preliminary_full_text_assistance",
        headline="Preliminary RoB 2 assistance available",
        explanation=(
            "RoB 2 is applied result-by-result where EvidenceOS can identify an outcome. "
            "NI/unresolved responses are preserved rather than guessed; human verification remains required."
        ),
        overall_judgement="outcome_specific",
        outcome_assessments=assessments,
    )


def assess_full_text(report_id: str, title: str, text: str) -> UniversalTrustAssessment:
    design = detect_design(title, text)

    if design == "randomized_controlled_trial":
        return _rct(report_id, title, text)
    if design in {"systematic_review", "meta_analysis"}:
        return _systematic_review(text, design)
    if design == "diagnostic_accuracy":
        return _diagnostic(text)
    if design == "qualitative":
        return _qualitative(text)
    if design in {"cohort", "case_control", "cross_sectional", "nonrandomized_intervention"}:
        result = _generic_observational(text, design)
        if design == "nonrandomized_intervention":
            result.framework = "ROBINS-I-oriented appraisal"
            result.limitations.append(
                "A formal ROBINS-I assessment additionally requires a target trial and prespecified important confounders."
            )
        return result

    if design == "protocol":
        return UniversalTrustAssessment(
            design=design,
            framework="Protocol reporting appraisal",
            status="preliminary_full_text_assistance",
            headline="Protocol detected",
            explanation="Protocols do not provide completed effect estimates; appraisal focuses on planned methodological safeguards.",
            overall_judgement="not_an_effect_estimate",
            domains=[],
        )

    if design == "guideline":
        return UniversalTrustAssessment(
            design=design,
            framework="Guideline appraisal scaffold",
            status="preliminary_full_text_assistance",
            headline="Guideline detected",
            explanation="Guideline trustworthiness requires a guideline-specific framework and panel/process information.",
            overall_judgement="human_verification_required",
            domains=[],
        )

    return UniversalTrustAssessment(
        design=design,
        framework="Generic methodological appraisal scaffold",
        status="preliminary_full_text_assistance",
        headline="Study design requires reviewer confirmation",
        explanation=(
            "EvidenceOS could not confidently route this report to a validated design-specific framework. "
            "It therefore withholds a risk-of-bias label."
        ),
        overall_judgement="unresolved",
        domains=[],
        limitations=["Confirm the study design before interpreting methodological trustworthiness."],
    )
