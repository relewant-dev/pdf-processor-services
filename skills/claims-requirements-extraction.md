# claims-requirements-extraction

## Purpose
Guide the **claims-requirements-extraction** capability for turning insurance policy claim conditions into actionable intake and submission checklists.

## Inputs
- Insurance policy text or extracted structured facts
- Claim scenario, loss date, policy period, and claimant context when available
- Compliance constraints for privacy, jurisdiction, or workflow integration

## Outputs
- Claim notice and submission checklist with required documents, forms, evidence, dates, and recipients
- Deadlines, waiting periods, proof-of-loss requirements, cooperation duties, and escalation paths
- Missing-information prompts and field-level validation warnings
- Structured handoff payload for claims intake or case-management systems

## Workflow
1. Locate claim notice, proof-of-loss, cooperation, appraisal, dispute, and limitation clauses.
2. Extract deadlines relative to incident date, discovery date, notice date, or policy effective dates.
3. Identify required evidence, forms, contacts, delivery channels, and escalation steps.
4. Validate whether key scenario facts are present and ask for missing facts explicitly.
5. Generate a concise checklist plus machine-readable fields for downstream workflows.

## Operational guidance
- Do not log sensitive claim details unless explicitly required and approved by policy.
- Clearly mark deadlines that are inferred from relative wording rather than explicit dates.
- Highlight incomplete policy text, unreadable OCR regions, and missing endorsements.
- Recommend human review for missed-deadline risk, denial-risk language, or complex disputes.
