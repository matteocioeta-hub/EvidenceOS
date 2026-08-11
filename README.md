# EvidenceOS

**EvidenceOS** is an alpha-stage research software engine for auditable scientific evidence extraction.

Its core design principle is:

> A model may propose an extraction; EvidenceOS separately verifies provenance and checks internal consistency before treating the field as trustworthy.

## Alpha scope

The public alpha focuses on **structured extraction from report text**. It exposes a Universal Evidence Record with:

- distinct screened / randomized / analysed sample sets;
- study arms and derived totals;
- outcomes, instruments and timepoints;
- effect estimates and statistical interpretation;
- source provenance;
- field-level epistemic status;
- consistency alarms.

Experimental modules for retrieval, RoB 2, synthesis, challenge, and gap falsification are included in the source tree but **are not validated product claims**.

## Epistemic statuses

Each field can be:

- `verified`
- `derived`
- `ambiguous`
- `conflicting`
- `not_reported`
- `unverified`

## Consistency alarms

The alpha can surface errors such as:

- `ARM_TOTAL_MISMATCH`
- `ATTRITION_PRESENT`
- `CI_SIGNIFICANCE_CONFLICT`
- `P_SIGNIFICANCE_CONFLICT`
- `DIRECTION_SIGNIFICANCE_CONFLICT`

## Install from source

```bash
python -m venv .venv
source .venv/bin/activate
pip install .
```

Development install:

```bash
pip install -e ".[dev]"
pytest
```

## CLI

```bash
evidenceos extract report.txt \
  --report-id RCT-001 \
  --title "Example randomized trial" \
  --output record.json
```

Run the API/UI:

```bash
evidenceos serve
```

Then open `http://127.0.0.1:8000`.

## REST API

```bash
curl -X POST http://127.0.0.1:8000/v1/extract \
  -H "Content-Type: application/json" \
  -d '{
    "report_id":"RCT-001",
    "title":"Example trial",
    "text":"Thirty-eight participants ... "
  }'
```

## Docker

```bash
docker build -t evidenceos:0.1.0a1 .
docker run --rm -p 8000:8000 evidenceos:0.1.0a1
```

## Scientific status

EvidenceOS is **research software in alpha**.

It must not be used as a substitute for independent methodological judgement, clinical decision-making, regulatory review, or publication-grade systematic review workflows without human verification.

The current benchmark program explicitly separates development cases from blind validation cases.

See:
- `docs/VALIDATION.md`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`

## License

This release candidate is distributed as **proprietary / all rights reserved** while the commercial and open-source licensing strategy is being finalized. See `LICENSE`.

## Citation

See `CITATION.cff`.
