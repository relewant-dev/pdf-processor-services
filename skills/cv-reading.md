# cv-reading

## Purpose
Guide the **cv-reading** capability for CVs, resumes, candidate profiles, academic CVs, portfolios, and role-specific application documents.

## Inputs
- Document source (path/URI or extracted text)
- Target role or evaluation context when available
- Optional language, region, seniority level, and compliance constraints

## Outputs
- Concise candidate summary grounded only in the supplied CV content
- Structured candidate facts: name, contact channels, location, target role, work history, education, certifications, projects, publications, languages, and links
- Experience timeline with employers, titles, date ranges, duration estimates, responsibilities, achievements, and evidence snippets when available
- Skills matrix grouped by technical skills, domain expertise, leadership, tools, and languages, with role/project evidence and confidence notes
- Warnings for missing chronology, unexplained gaps, stale contact details, contradictory dates, unsupported skill claims, and low-confidence OCR spans

## Workflow
1. Classify the document as a CV, resume, academic CV, or candidate profile before extraction.
2. Extract identity and contact fields, but avoid echoing unnecessary sensitive details in summaries.
3. Build a chronological experience timeline and normalize date ranges, ongoing roles, overlaps, and gaps.
4. Map skills to supporting evidence from roles, projects, education, or certifications instead of inferring unsupported capabilities.
5. Summarize strengths, role fit signals, missing information, and human-review questions without making hiring decisions.

## Operational guidance
- Treat CV content as personal data; minimize PII in logs and outputs.
- Do not infer protected attributes or make discriminatory recommendations.
- Prefer “not found in provided CV” over guessing when fields are missing.
- Preserve field-level confidence and source references when extraction tooling provides them.
