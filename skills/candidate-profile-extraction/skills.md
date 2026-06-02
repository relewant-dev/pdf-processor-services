# candidate-profile-extraction

## Purpose
Provide guidance for the **candidate-profile-extraction** capability that converts CV/resume text into a structured, reviewable candidate profile.

## Inputs
- CV/resume source (path/URI or extracted text)
- Optional target role profile, seniority expectations, and required schema
- Processing context such as language, region, and privacy constraints

## Outputs
- Structured candidate profile with identity, contact, work history, education, certifications, projects, skills, languages, and links
- Field-level confidence, source references, and “not found” markers for absent fields
- Review notes for ambiguous titles, unknown employers, incomplete dates, and possible OCR/layout issues

## Workflow
1. Validate that the input is readable CV/resume content and identify its language and layout.
2. Extract sections in order: header/contact, summary, experience, education, certifications, projects, skills, languages, publications, awards, and links.
3. Normalize names of employers, schools, certifications, technologies, locations, and date formats without changing meaning.
4. Attach source evidence and confidence to each extracted field.
5. Return a deterministic structured profile plus human-readable review notes.

## Operational guidance
- Keep extraction evidence-backed and avoid adding facts from outside sources.
- Redact or suppress unnecessary sensitive personal data when the downstream task does not require it.
- Represent missing values explicitly rather than omitting required schema keys.
