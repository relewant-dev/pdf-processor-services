# coverage-exclusions-analysis

## Purpose
Guide the **coverage-exclusions-analysis** capability for comparing claimed scenarios against policy coverage grants, limits, exclusions, and endorsements.

## Inputs
- Extracted insurance policy facts and clause text
- User scenario or claim question
- Coverage profile (line of business, jurisdiction, product type, compliance mode)

## Outputs
- Scenario-to-coverage mapping with covered, excluded, conditional, and unknown statuses
- Limits, sublimits, deductibles, waiting periods, and endorsement impacts
- Exclusion and exception summary with confidence and source locations when available
- Human-review warnings for ambiguous, conflicting, or jurisdiction-sensitive clauses

## Workflow
1. Normalize the user scenario into events, parties, property, dates, losses, and requested benefits.
2. Match scenario elements to coverage grants and declarations-page limits.
3. Check exclusions, exceptions to exclusions, endorsements, riders, and conditions precedent.
4. Produce a decision-support matrix without making binding coverage determinations.
5. Surface gaps, conflicts, missing facts, and recommended next questions.

## Operational guidance
- Treat the policy text as the source of truth and avoid external assumptions about coverage.
- Separate factual extraction from interpretation and recommendation.
- Preserve confidence scores per clause and per scenario mapping.
- Include clear disclaimers when the answer requires insurer, broker, legal, or licensed professional review.
