# experience-skills-normalization

## Purpose
Guide the **experience-skills-normalization** capability for turning free-form CV experience and skill sections into a consistent timeline and skills matrix.

## Inputs
- Extracted CV sections or full CV text
- Optional target role taxonomy, technology taxonomy, seniority rubric, and date normalization rules

## Outputs
- Normalized experience timeline with date ranges, durations, overlaps, gaps, titles, organizations, and evidence-backed achievements
- Skills matrix grouped by category with proficiency evidence, recency signals, and role/project references
- Warnings for ambiguous dates, unsupported skill claims, inflated keyword lists, duplicate roles, and chronology conflicts

## Workflow
1. Parse all date expressions, including month/year ranges, years-only ranges, “present,” and academic periods.
2. Sort roles chronologically and compute approximate durations while preserving uncertainty.
3. Link technologies and skills to the roles, projects, or certifications where they appear.
4. Detect chronology gaps, overlapping positions, repeated employers, and inconsistent titles.
5. Produce normalized values suitable for search, matching, summaries, and reviewer handoff.

## Operational guidance
- Never convert uncertainty into false precision; mark approximate dates clearly.
- Do not score candidate suitability unless a separate, compliant evaluation rubric is supplied.
- Avoid deriving protected or sensitive attributes from names, dates, locations, or institutions.
