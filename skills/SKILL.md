# SKILL.md

This folder contains reusable document-processing skills for MCP intent routing.

## Document-processing skills

Insurance document requests should use the `insurance-document-reader-agent` alongside:

- `insurance-policy-reading` when the user asks to read, summarize, or extract facts from an insurance policy.
- `coverage-exclusions-analysis` when the user asks whether a scenario appears covered, excluded, conditional, or unclear from the supplied policy text.
- `claims-requirements-extraction` when the user asks what is needed to submit or prepare a claim.

These skills are document-reading support only. They should avoid legal or licensed-insurance advice and should flag ambiguous or missing policy text for human review.

CV and resume requests should use the `cv-reader-agent` alongside:

- `cv-reading` when the user asks to read, summarize, or extract facts from a CV/resume.
- `candidate-profile-extraction` when the user needs structured candidate data for review or downstream systems.
- `experience-skills-normalization` when the user needs normalized timelines, skills matrices, gap detection, or role/project evidence.

These skills are document-reading support only. They should protect candidate PII, avoid protected-attribute inference, and avoid making hiring decisions without a separate compliant review process.
