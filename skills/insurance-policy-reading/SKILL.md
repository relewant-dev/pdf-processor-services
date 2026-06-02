# insurance-policy-reading

## Purpose
Guide the **insurance-policy-reading** capability for insurance documents such as policy declarations, schedules, endorsements, certificates of insurance, claim forms, and renewal notices.

## Inputs
- Document source (path/URI or extracted text)
- Insurance context (line of business, jurisdiction, policyholder question, compliance constraints)
- Optional policy profile with expected products, coverages, and claim scenario

## Outputs
- Plain-language coverage summary with citations to extracted clauses when available
- Structured policy facts: insurer, policyholder, policy number, effective dates, limits, deductibles, premiums, endorsements, exclusions, and cancellation/renewal terms
- Claim-readiness notes: notice requirements, evidence checklist, deadlines, contacts, and escalation paths
- Confidence indicators, ambiguities, missing pages/schedules, and recommended human-review items

## Workflow
1. Classify the insurance document subtype and line of business before extraction.
2. Extract declarations-page facts first, then reconcile schedules, riders, and endorsements.
3. Identify covered events, limits, sublimits, deductibles, exclusions, waiting periods, and conditions precedent.
4. Map claim obligations to a checklist with dates, evidence requirements, contacts, and unresolved dependencies.
5. Flag contradictions, ambiguous wording, missing attachments, low-confidence OCR spans, and clauses requiring licensed insurance/legal review.

## Operational guidance
- Do not present coverage determinations as legal advice; frame results as document-reading support.
- Preserve sensitive personal, health, financial, and claims data boundaries in logs and outputs.
- Keep extracted clause references and field confidence attached to each coverage or claim finding.
- Prefer explicit “not found in provided document” messages over inference when the policy text is incomplete.
