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


def _signal(name: str, present: bool, yes: str, no: str) -> AppraisalDomain:
    return AppraisalDomain(
        domain=name,
        judgement="signal_present" if present else "unresolved",
        rationale=yes if present else no,
    )


def _assessment(
    design: str,
    framework: str,
    headline: str,
    explanation: str,
    domains: list[AppraisalDomain],
    limitations: list[str] | None = None,
) -> UniversalTrustAssessment:
    resolved = sum(d.judgement == "signal_present" for d in domains)
    return UniversalTrustAssessment(
        design=design,
        framework=framework,
        status="preliminary_full_text_assistance",
        headline=headline,
        explanation=explanation,
        overall_judgement=(
            "substantial_information_available"
            if domains and resolved >= max(2, int(len(domains) * 0.7))
            else "human_verification_required"
        ),
        domains=domains,
        limitations=limitations or [],
    )


def detect_design(title: str, text: str) -> str:
    blob = f"{title}\n{text[:25000]}"

    # Evidence syntheses first.
    if _has(blob, r"\bnetwork meta[- ]analysis\b"):
        return "network_meta_analysis"
    if _has(blob, r"\bmeta[- ]analysis\b", r"\bmeta analysis\b"):
        return "meta_analysis"
    if _has(blob, r"\bsystematic review\b"):
        return "systematic_review"
    if _has(blob, r"\bscoping review\b"):
        return "scoping_review"

    # Specialised designs.
    if _has(blob, r"\bdiagnostic accuracy\b", r"\bsensitivity\b.{0,80}\bspecificity\b", r"\bindex test\b"):
        return "diagnostic_accuracy"
    if _has(blob, r"\bprediction model\b", r"\bprognostic model\b", r"\bclinical prediction rule\b"):
        return "prediction_model"
    if _has(blob, r"\bcost[- ]effectiveness\b", r"\bcost utility\b", r"\beconomic evaluation\b"):
        return "economic_evaluation"
    if _has(blob, r"\bclinical practice guideline\b", r"\bguideline\b"):
        return "guideline"

    # Qualitative.
    if _has(blob, r"\bqualitative\b", r"\bthematic analysis\b", r"\bphenomenolog", r"\bgrounded theory\b"):
        return "qualitative"

    # Experimental/intervention.
    if _has(blob, r"\brandomi[sz](?:ed|ation)\b", r"\brandomly assigned\b"):
        return "randomized_controlled_trial"
    if _has(blob, r"\bquasi[- ]experimental\b", r"\bnon[- ]randomi[sz]ed\b", r"\bcontrolled before[- ]after\b"):
        return "nonrandomized_intervention"

    # Observational.
    if _has(blob, r"\bcase[- ]control\b"):
        return "case_control"
    if _has(blob, r"\bcross[- ]sectional\b"):
        return "cross_sectional"
    if _has(blob, r"\bprevalence\b", r"\bpoint prevalence\b", r"\bperiod prevalence\b"):
        return "prevalence"
    if _has(blob, r"\bcase series\b"):
        return "case_series"
    if _has(blob, r"\bcase report\b"):
        return "case_report"
    if _has(blob, r"\bcohort\b", r"\bprospective observational\b", r"\bretrospective observational\b"):
        return "cohort"

    if _has(blob, r"\bprotocol\b"):
        return "protocol"
    return "other"


def _rct(report_id: str, title: str, text: str) -> UniversalTrustAssessment:
    # Keep bounded for synchronous cloud execution.
    extraction = ExtractionEngine().extract(report_id, title, text[:80000])
    engine = RoB2Engine()
    assessments = []
    targets = extraction.outcomes[:3] if extraction.outcomes else [None]

    for result in targets:
        rid = result.result_id if result else None
        rob = engine.assess(extraction, result_id=rid)
        assessments.append({
            "result_id": rid,
            "outcome": result.outcome_name if result else "Outcome not deterministically mapped",
            "timepoint": result.timepoint if result else None,
            "effect_measure": result.effect_measure if result else None,
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
        framework="EvidenceOS RCT bias engine (RoB 2-aligned concepts)",
        status="preliminary_full_text_assistance",
        headline="Outcome-specific randomized-trial appraisal",
        explanation=(
            "EvidenceOS applies its own deterministic implementation of core randomized-trial "
            "bias concepts. This commercial software does not claim to reproduce the official "
            "RoB 2 instrument. Human verification remains required."
        ),
        overall_judgement="outcome_specific",
        outcome_assessments=assessments,
        limitations=[
            "At most three deterministically mapped outcomes are assessed in one synchronous request.",
            "Formal use of third-party proprietary/licensed tools may require separate permission.",
        ],
    )


def _nrsi(text: str) -> UniversalTrustAssessment:
    domains = [
        _signal("Confounding", _has(text, r"\bconfound", r"\badjusted for\b", r"\bpropensity", r"\binverse probability weighting\b"),
                "Confounding/adjustment strategy detected.", "Important confounders and adequacy of control require verification."),
        _signal("Classification of intervention", _has(text, r"\bintervention classification\b", r"\bexposure classification\b", r"\btreatment group\b"),
                "Intervention classification information detected.", "Misclassification of intervention remains unresolved."),
        _signal("Selection into the study", _has(text, r"\beligib", r"\binclusion criteria\b", r"\bexclusion criteria\b"),
                "Selection/eligibility information detected.", "Selection mechanisms require verification."),
        _signal("Deviations from intended intervention", _has(text, r"\bdeviation", r"\badherence\b", r"\bcrossover\b", r"\bco-intervention\b"),
                "Intervention-deviation/adherence information detected.", "Bias from deviations remains unresolved."),
        _signal("Missing data", _has(text, r"\bmissing data\b", r"\blost to follow", r"\bmultiple imputation\b"),
                "Missing-data information detected.", "Amount, mechanism and handling of missingness require verification."),
        _signal("Outcome measurement", _has(text, r"\bvalidated\b", r"\bblinded assessor\b", r"\bobjective outcome\b"),
                "Outcome-measurement safeguard detected.", "Differential or biased measurement remains unresolved."),
        _signal("Selection of reported result", _has(text, r"\bprotocol\b", r"\bregistration\b", r"\bstatistical analysis plan\b"),
                "Prespecification signal detected.", "Selective reporting cannot be excluded automatically."),
    ]
    return _assessment(
        "nonrandomized_intervention",
        "EvidenceOS non-randomized intervention bias engine (ROBINS-I-oriented concepts)",
        "Non-randomized intervention appraisal",
        "The engine evaluates major bias mechanisms relevant to non-randomized intervention studies without reproducing the official ROBINS-I instrument.",
        domains,
        [
            "A formal ROBINS-I assessment requires review-specific specification of the target trial and important confounders.",
            "This output is not an official ROBINS-I judgement.",
        ],
    )


def _cohort(text: str) -> UniversalTrustAssessment:
    return _assessment(
        "cohort",
        "EvidenceOS cohort risk-of-bias engine (JBI-oriented constructs)",
        "Cohort study appraisal",
        "Full-text signals are organised around selection, exposure, confounding, follow-up, outcome measurement and analysis.",
        [
            _signal("Selection and group comparability", _has(text, r"\binclusion criteria\b", r"\bexposed group\b", r"\bunexposed group\b"), "Selection/comparator information detected.", "Selection and comparability require verification."),
            _signal("Exposure measurement", _has(text, r"\bvalidated\b.{0,80}\bexposure\b", r"\bexposure was measured\b"), "Exposure measurement information detected.", "Exposure validity/reliability unresolved."),
            _signal("Confounding", _has(text, r"\bconfound", r"\badjusted for\b", r"\bmultivariable\b"), "Confounder handling detected.", "Residual/unmeasured confounding unresolved."),
            _signal("Outcome at baseline / temporality", _has(text, r"\bbaseline\b", r"\bfollow[- ]up\b"), "Temporal information detected.", "Temporality requires verification."),
            _signal("Follow-up and missingness", _has(text, r"\blost to follow", r"\battrition\b", r"\bcomplete follow-up\b"), "Follow-up information detected.", "Completeness and differential loss unresolved."),
            _signal("Outcome measurement and analysis", _has(text, r"\bvalidated outcome\b", r"\bcox regression\b", r"\blogistic regression\b", r"\bregression model\b"), "Outcome/analysis signal detected.", "Outcome ascertainment and model adequacy unresolved."),
        ],
    )


def _case_control(text: str) -> UniversalTrustAssessment:
    return _assessment(
        "case_control",
        "EvidenceOS case-control bias engine (JBI-oriented constructs)",
        "Case-control study appraisal",
        "The engine focuses on case definition, control selection, exposure ascertainment, confounding and analysis.",
        [
            _signal("Case definition", _has(text, r"\bcase definition\b", r"\bdiagnostic criteria\b"), "Case-definition signal detected.", "Validity of case definition unresolved."),
            _signal("Control selection", _has(text, r"\bcontrols were selected\b", r"\bcontrol group\b"), "Control-selection information detected.", "Source-population comparability unresolved."),
            _signal("Exposure ascertainment", _has(text, r"\bexposure\b", r"\bmedical records\b", r"\binterview\b"), "Exposure-ascertainment signal detected.", "Recall/differential ascertainment unresolved."),
            _signal("Comparable ascertainment", _has(text, r"\bsame method\b", r"\bblinded\b"), "Comparable/blinded ascertainment signal detected.", "Differential measurement unresolved."),
            _signal("Confounding", _has(text, r"\bmatching\b", r"\badjusted for\b", r"\bconfound"), "Matching/adjustment signal detected.", "Residual confounding unresolved."),
            _signal("Analysis", _has(text, r"\bodds ratio\b", r"\blogistic regression\b"), "Case-control analysis signal detected.", "Analysis specification and reporting require verification."),
        ],
    )


def _cross_sectional(text: str) -> UniversalTrustAssessment:
    return _assessment(
        "cross_sectional",
        "EvidenceOS analytical cross-sectional bias engine (revised JBI-oriented constructs)",
        "Cross-sectional study appraisal",
        "The engine separates sampling, exposure/outcome measurement, confounding and analysis rather than generating a checklist score.",
        [
            _signal("Sampling frame and recruitment", _has(text, r"\bsampling frame\b", r"\brandom sample\b", r"\bconsecutive\b"), "Sampling strategy detected.", "Representativeness/selection bias unresolved."),
            _signal("Eligibility criteria", _has(text, r"\binclusion criteria\b", r"\bexclusion criteria\b"), "Eligibility criteria detected.", "Eligibility definition unresolved."),
            _signal("Exposure measurement", _has(text, r"\bvalidated\b", r"\breliable\b"), "Measurement-quality signal detected.", "Exposure measurement validity unresolved."),
            _signal("Outcome measurement", _has(text, r"\bdiagnostic criteria\b", r"\bvalidated outcome\b"), "Outcome-definition signal detected.", "Outcome ascertainment unresolved."),
            _signal("Confounding", _has(text, r"\bconfound", r"\badjusted for\b", r"\bmultivariable\b"), "Confounding strategy detected.", "Residual confounding unresolved."),
            _signal("Statistical analysis", _has(text, r"\bregression\b", r"\bconfidence interval\b", r"\bp value\b"), "Statistical-analysis signal detected.", "Model assumptions/precision require verification."),
        ],
    )


def _prevalence(text: str) -> UniversalTrustAssessment:
    return _assessment(
        "prevalence",
        "EvidenceOS prevalence-study appraisal (JBI-oriented constructs)",
        "Prevalence study appraisal",
        "The engine focuses on representativeness, sampling, condition measurement, response and precision.",
        [
            _signal("Representative sampling frame", _has(text, r"\bpopulation-based\b", r"\brandom sample\b"), "Population/sampling-frame signal detected.", "Representativeness unresolved."),
            _signal("Sampling method", _has(text, r"\brandom sampling\b", r"\bcluster sampling\b", r"\bstratified sampling\b"), "Probability-sampling signal detected.", "Sampling bias unresolved."),
            _signal("Adequate sample planning", _has(text, r"\bsample size calculation\b", r"\bpower calculation\b"), "Sample-size planning detected.", "Precision planning unresolved."),
            _signal("Condition measurement", _has(text, r"\bdiagnostic criteria\b", r"\bvalidated\b"), "Condition-measurement signal detected.", "Measurement validity unresolved."),
            _signal("Response / coverage", _has(text, r"\bresponse rate\b", r"\bnon-response\b"), "Response information detected.", "Non-response bias unresolved."),
            _signal("Prevalence estimation", _has(text, r"\bprevalence\b.{0,80}\bconfidence interval\b"), "Prevalence precision signal detected.", "Estimation/weighting details unresolved."),
        ],
    )


def _diagnostic(text: str) -> UniversalTrustAssessment:
    return _assessment(
        "diagnostic_accuracy",
        "EvidenceOS diagnostic accuracy engine (QUADAS-3-oriented concepts)",
        "Diagnostic accuracy appraisal",
        "The current QUADAS-3 framework is estimate-level. EvidenceOS therefore treats these as preliminary estimate-relevant signals, not a formal QUADAS-3 assessment.",
        [
            _signal("Participants", _has(text, r"\bconsecutive\b", r"\brandom sample\b", r"\bpatient spectrum\b"), "Participant-selection signal detected.", "Participant selection/applicability unresolved."),
            _signal("Index test", _has(text, r"\bindex test\b", r"\bthreshold\b", r"\bblinded\b"), "Index-test methods detected.", "Threshold/interpretation bias unresolved."),
            _signal("Target condition", _has(text, r"\breference standard\b", r"\btarget condition\b"), "Target-condition/reference-standard signal detected.", "Target-condition classification unresolved."),
            _signal("Analysis", _has(text, r"\bsensitivity\b", r"\bspecificity\b", r"\broc\b", r"\bauc\b"), "Accuracy-analysis signal detected.", "Estimate-specific exclusions/analysis choices unresolved."),
        ],
        [
            "A formal QUADAS-3 appraisal must be anchored to a synthesis question, ideal test accuracy trial and selected accuracy estimate.",
        ],
    )


def _systematic_review(text: str, design: str) -> UniversalTrustAssessment:
    domains = [
        _signal("Protocol and a priori methods", _has(text, r"\bprospero\b", r"\bprotocol\b.{0,80}\bregistered\b"), "Protocol/registration detected.", "Prospective protocol not verified."),
        _signal("Search comprehensiveness", sum(bool(_has(text, p)) for p in [r"\bpubmed\b", r"\bmedline\b", r"\bembase\b", r"\bcinahl\b", r"\bweb of science\b"]) >= 2, "Multiple databases detected.", "Search coverage unresolved."),
        _signal("Duplicate study processes", _has(text, r"\btwo reviewers\b", r"\bindependently\b.{0,80}\breviewer"), "Duplicate/independent process detected.", "Study selection/extraction duplication unresolved."),
        _signal("Risk-of-bias methods", _has(text, r"\brisk of bias\b", r"\bcritical appraisal\b"), "Risk-of-bias appraisal detected.", "Appropriateness of appraisal unresolved."),
        _signal("Synthesis methods", _has(text, r"\brandom[- ]effects\b", r"\bfixed[- ]effect\b", r"\bmeta[- ]analysis\b", r"\bnarrative synthesis\b"), "Synthesis-method signal detected.", "Suitability of synthesis assumptions unresolved."),
        _signal("Heterogeneity", _has(text, r"\bi\^?2\b", r"\bheterogeneity\b", r"\btau"), "Heterogeneity assessment detected.", "Exploration/interpretation of heterogeneity unresolved."),
        _signal("Small-study/publication bias", _has(text, r"\bfunnel plot\b", r"\begger\b", r"\bpublication bias\b"), "Small-study/publication-bias assessment detected.", "Publication bias unresolved."),
        _signal("Conflicts and funding", _has(text, r"\bconflict of interest\b", r"\bfunding\b"), "Funding/conflict information detected.", "Influence of conflicts/funding unresolved."),
    ]
    return _assessment(
        design,
        "EvidenceOS systematic-review appraisal (AMSTAR 2-oriented critical domains)",
        "Systematic review appraisal",
        "AMSTAR 2 is not a numerical score; EvidenceOS similarly reports domain signals and critical weaknesses rather than summing points.",
        domains,
        ["This is not an official AMSTAR 2 assessment unless separately licensed/validated."],
    )


def _qualitative(text: str) -> UniversalTrustAssessment:
    return _assessment(
        "qualitative",
        "EvidenceOS qualitative appraisal (JBI/CASP-oriented constructs)",
        "Qualitative study appraisal",
        "Interpretive research requires human methodological judgement; EvidenceOS highlights auditable signals rather than generating a quality score.",
        [
            _signal("Congruity of methodology and question", _has(text, r"\bqualitative\b", r"\bphenomenolog", r"\bgrounded theory\b", r"\bethnograph"), "Methodological approach identified.", "Methodological congruity unresolved."),
            _signal("Sampling and recruitment", _has(text, r"\bpurposive\b", r"\bpurposeful\b", r"\bmaximum variation\b", r"\btheoretical sampling\b"), "Sampling strategy detected.", "Sampling adequacy unresolved."),
            _signal("Data collection", _has(text, r"\bsemi[- ]structured interview\b", r"\bfocus group\b", r"\bobservation\b"), "Data-collection method detected.", "Depth/appropriateness of collection unresolved."),
            _signal("Researcher reflexivity", _has(text, r"\breflexiv", r"\bresearcher positioning\b", r"\bpositionality\b"), "Reflexivity signal detected.", "Researcher influence/relationship unresolved."),
            _signal("Analysis", _has(text, r"\bthematic analysis\b", r"\bframework analysis\b", r"\bconstant comparative\b"), "Analytic method detected.", "Analytic rigor and auditability unresolved."),
            _signal("Grounding of findings", _has(text, r"\bparticipant quote\b", r"\bverbatim\b", r"\bquotation\b"), "Participant-data grounding signal detected.", "Data-to-theme grounding unresolved."),
            _signal("Ethics", _has(text, r"\bethics approval\b", r"\binformed consent\b"), "Ethics/consent signal detected.", "Ethical conduct unresolved."),
        ],
    )


def _case_series(text: str) -> UniversalTrustAssessment:
    return _assessment(
        "case_series",
        "EvidenceOS case-series appraisal (JBI-oriented constructs)",
        "Case series appraisal",
        "The engine assesses clarity and completeness of case definition, inclusion, measurement and reporting.",
        [
            _signal("Clear inclusion criteria", _has(text, r"\binclusion criteria\b"), "Inclusion criteria detected.", "Case inclusion criteria unresolved."),
            _signal("Reliable condition measurement", _has(text, r"\bdiagnostic criteria\b", r"\bconfirmed by\b"), "Condition ascertainment signal detected.", "Reliability of diagnosis unresolved."),
            _signal("Consecutive/complete inclusion", _has(text, r"\bconsecutive\b", r"\ball eligible\b"), "Consecutive/complete inclusion signal detected.", "Selection of cases unresolved."),
            _signal("Participant characteristics", _has(text, r"\bmean age\b", r"\bmedian age\b", r"\bsex\b", r"\bgender\b"), "Participant description detected.", "Completeness of participant description unresolved."),
            _signal("Clinical information/outcomes", _has(text, r"\boutcome\b", r"\bfollow[- ]up\b", r"\btreatment\b"), "Clinical course/outcome signal detected.", "Completeness of clinical reporting unresolved."),
        ],
    )


def _case_report(text: str) -> UniversalTrustAssessment:
    return _assessment(
        "case_report",
        "EvidenceOS case-report appraisal (JBI-oriented constructs)",
        "Case report appraisal",
        "Case reports are appraised for diagnostic/clinical clarity and completeness rather than comparative causal inference.",
        [
            _signal("Patient description", _has(text, r"\byear[- ]old\b", r"\bpatient\b"), "Patient-description signal detected.", "Patient characteristics unresolved."),
            _signal("History/timeline", _has(text, r"\bhistory\b", r"\btimeline\b"), "History/timeline signal detected.", "Clinical timeline unresolved."),
            _signal("Diagnostic assessment", _has(text, r"\bdiagnos", r"\bimaging\b", r"\blaboratory\b"), "Diagnostic work-up signal detected.", "Diagnostic reasoning unresolved."),
            _signal("Intervention", _has(text, r"\btreatment\b", r"\bintervention\b", r"\btherapy\b"), "Intervention information detected.", "Intervention detail unresolved."),
            _signal("Follow-up/outcome", _has(text, r"\bfollow[- ]up\b", r"\boutcome\b"), "Follow-up/outcome signal detected.", "Outcome completeness unresolved."),
        ],
    )


def _prediction_model(text: str) -> UniversalTrustAssessment:
    return _assessment(
        "prediction_model",
        "EvidenceOS prediction-model appraisal (PROBAST-oriented concepts)",
        "Prediction model appraisal",
        "The engine structures signals around participants, predictors, outcome and analysis.",
        [
            _signal("Participants", _has(text, r"\binclusion criteria\b", r"\bcohort\b"), "Participant-selection signal detected.", "Participant selection/applicability unresolved."),
            _signal("Predictors", _has(text, r"\bpredictor\b", r"\bcandidate variable\b"), "Predictor-definition signal detected.", "Predictor assessment/blinding unresolved."),
            _signal("Outcome", _has(text, r"\boutcome definition\b", r"\bprimary outcome\b"), "Outcome-definition signal detected.", "Outcome ascertainment unresolved."),
            _signal("Analysis", _has(text, r"\bcalibration\b", r"\bdiscrimination\b", r"\bc[- ]statistic\b", r"\bauc\b"), "Model-performance analysis detected.", "Overfitting, sample size and validation require verification."),
        ],
        ["Formal PROBAST/PROBAST+AI use may require review-specific signalling judgements."],
    )


def _economic(text: str) -> UniversalTrustAssessment:
    return _assessment(
        "economic_evaluation",
        "EvidenceOS economic-evaluation appraisal",
        "Economic evaluation appraisal",
        "The engine examines perspective, comparators, costs/outcomes, time horizon, discounting and uncertainty.",
        [
            _signal("Perspective", _has(text, r"\bhealthcare perspective\b", r"\bsocietal perspective\b", r"\bperspective\b"), "Economic perspective detected.", "Perspective unresolved."),
            _signal("Comparators", _has(text, r"\bcomparator\b", r"\busual care\b"), "Comparator signal detected.", "Relevance/completeness of alternatives unresolved."),
            _signal("Costs and outcomes", _has(text, r"\bcost\b", r"\bqaly\b", r"\butility\b"), "Cost/outcome measurement detected.", "Valuation validity unresolved."),
            _signal("Time horizon / discounting", _has(text, r"\btime horizon\b", r"\bdiscount rate\b", r"\bdiscounted\b"), "Time/discounting signal detected.", "Appropriateness unresolved."),
            _signal("Incremental analysis", _has(text, r"\bicer\b", r"\bincremental cost[- ]effectiveness\b"), "Incremental analysis detected.", "Incremental-method validity unresolved."),
            _signal("Uncertainty", _has(text, r"\bsensitivity analysis\b", r"\bprobabilistic sensitivity\b"), "Uncertainty analysis detected.", "Structural/parameter uncertainty unresolved."),
        ],
    )


def _guideline(text: str) -> UniversalTrustAssessment:
    return _assessment(
        "guideline",
        "EvidenceOS guideline appraisal (AGREE-style domains)",
        "Clinical guideline appraisal",
        "Guidelines require appraisal of scope, stakeholders, development rigour, clarity, applicability and editorial independence.",
        [
            _signal("Scope and purpose", _has(text, r"\bscope\b", r"\bobjective\b", r"\btarget population\b"), "Scope/purpose signal detected.", "Scope clarity unresolved."),
            _signal("Stakeholder involvement", _has(text, r"\bpatient representative\b", r"\bstakeholder\b", r"\bmultidisciplinary panel\b"), "Stakeholder signal detected.", "Stakeholder breadth unresolved."),
            _signal("Rigour of development", _has(text, r"\bsystematic review\b", r"\bevidence search\b", r"\bgrade\b"), "Evidence-development process detected.", "Rigour/updates unresolved."),
            _signal("Clarity", _has(text, r"\brecommendation\b"), "Recommendations detected.", "Specificity/actionability unresolved."),
            _signal("Applicability", _has(text, r"\bimplementation\b", r"\bresource\b", r"\bbarrier\b"), "Implementation/applicability signal detected.", "Applicability planning unresolved."),
            _signal("Editorial independence", _has(text, r"\bconflict of interest\b", r"\bfunding\b"), "Conflict/funding information detected.", "Editorial independence unresolved."),
        ],
    )


def assess_full_text(report_id: str, title: str, text: str) -> UniversalTrustAssessment:
    bounded = text[:80000]
    design = detect_design(title, bounded)

    routes = {
        "randomized_controlled_trial": lambda: _rct(report_id, title, bounded),
        "nonrandomized_intervention": lambda: _nrsi(bounded),
        "cohort": lambda: _cohort(bounded),
        "case_control": lambda: _case_control(bounded),
        "cross_sectional": lambda: _cross_sectional(bounded),
        "prevalence": lambda: _prevalence(bounded),
        "diagnostic_accuracy": lambda: _diagnostic(bounded),
        "qualitative": lambda: _qualitative(bounded),
        "case_series": lambda: _case_series(bounded),
        "case_report": lambda: _case_report(bounded),
        "prediction_model": lambda: _prediction_model(bounded),
        "economic_evaluation": lambda: _economic(bounded),
        "guideline": lambda: _guideline(bounded),
        "systematic_review": lambda: _systematic_review(bounded, design),
        "meta_analysis": lambda: _systematic_review(bounded, design),
        "network_meta_analysis": lambda: _systematic_review(bounded, design),
    }
    if design in routes:
        return routes[design]()

    if design == "scoping_review":
        return _assessment(
            design,
            "EvidenceOS scoping-review methods appraisal",
            "Scoping review appraisal",
            "Scoping reviews are evaluated for transparent question, search, selection, charting and synthesis methods rather than intervention-effect risk of bias.",
            [
                _signal("Protocol", _has(bounded, r"\bprotocol\b", r"\bosf\b"), "Protocol signal detected.", "Protocol not verified."),
                _signal("Search", _has(bounded, r"\bpubmed\b", r"\bmedline\b", r"\bembase\b"), "Bibliographic search detected.", "Search comprehensiveness unresolved."),
                _signal("Selection", _has(bounded, r"\btwo reviewers\b", r"\bindependently\b"), "Independent selection signal detected.", "Selection process unresolved."),
                _signal("Data charting", _has(bounded, r"\bdata chart", r"\bdata extraction\b"), "Charting/extraction signal detected.", "Charting reliability unresolved."),
                _signal("Synthesis", _has(bounded, r"\bnarrative synthesis\b", r"\bdescriptive synthesis\b"), "Synthesis method detected.", "Synthesis transparency unresolved."),
            ],
        )

    if design == "protocol":
        return UniversalTrustAssessment(
            design=design,
            framework="EvidenceOS protocol appraisal",
            status="preliminary_full_text_assistance",
            headline="Protocol detected",
            explanation="Protocols are assessed for planned methodological safeguards, not completed effect estimates.",
            overall_judgement="not_an_effect_estimate",
            domains=[
                _signal("Clear objectives", _has(bounded, r"\bobjective\b", r"\baim\b"), "Objectives detected.", "Objectives unresolved."),
                _signal("Prespecified methods", _has(bounded, r"\bmethods\b", r"\bstatistical analysis\b"), "Methods signal detected.", "Method completeness unresolved."),
                _signal("Registration", _has(bounded, r"\bregistered\b", r"\bprospero\b", r"\bclinicaltrials\.gov\b"), "Registration detected.", "Registration not verified."),
            ],
        )

    return UniversalTrustAssessment(
        design="other",
        framework="EvidenceOS generic appraisal scaffold",
        status="preliminary_full_text_assistance",
        headline="Study design requires confirmation",
        explanation="EvidenceOS could not route this report confidently to a design-specific appraisal engine.",
        overall_judgement="unresolved",
        limitations=["Confirm the study design before interpreting methodological trustworthiness."],
    )
