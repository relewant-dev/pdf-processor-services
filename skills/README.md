# Skills Catalog

This directory contains reusable document-processing skills:

- `document-classification`
- `ocr-extraction`
- `structured-data-mapping`
- `pii-redaction`
- `document-validation`
- `fraud-signals-detection`
- `insurance-policy-reading`
- `coverage-exclusions-analysis`
- `claims-requirements-extraction`
- `cv-reading`
- `candidate-profile-extraction`
- `experience-skills-normalization`
- `document-processing-observability`

## Insurance document reading

Insurance-related prompts such as “read this insurance policy,” “summarize coverage,” or “extract claim requirements” should route to the document-processing blueprint and use the `insurance-document-reader-agent` with these skills:

- `insurance-policy-reading` for policy declarations, endorsements, limits, deductibles, exclusions, and renewal/cancellation terms.
- `coverage-exclusions-analysis` for mapping user scenarios to coverage grants, limits, exclusions, exceptions, and ambiguous clauses.
- `claims-requirements-extraction` for notice duties, proof-of-loss requirements, evidence checklists, deadlines, and escalation paths.

## CV and resume reading

CV/resume prompts such as “read this CV,” “summarize this resume,” or “extract candidate skills” should route to the document-processing blueprint and use the `cv-reader-agent` with these skills:

- `cv-reading` for evidence-backed summaries of candidate profile facts, work history, education, certifications, projects, languages, and warnings.
- `candidate-profile-extraction` for converting CV/resume text into structured candidate fields with confidence and source references.
- `experience-skills-normalization` for normalizing chronology, role durations, gaps, overlapping dates, technologies, and evidence-backed skills matrices.
