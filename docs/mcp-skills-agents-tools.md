# MCP Skill, Agent, and Tool Blueprint (Document Processing)

This document defines the active **skills**, **agents**, and **MCP tools** for document-processing workflows. Backend generation skills and their routing tools have been removed.


## Skill file layout

Each reusable skill is stored in its own directory under `skills/`, and the skill definition file is always named `skills.md`:

```text
skills/<skill-name>/skills.md
```

The `skills/` directory intentionally has no catalog `README.md`; use this blueprint document and the per-skill folders as the source of truth.

## 1) Document processing tools

For document-heavy workflows (invoices, CVs, resumes, forms), add the following MCP tools:

- `list_document_blueprint`: returns document-specific skills, agents, tools.
- `generate_document_skill_set(document_type, compliance_mode)`: prioritized capabilities and checklist.
- `generate_document_agent_plan(document_type, objective, constraints)`: multi-agent plan for extraction + validation.
- `generate_document_tool_spec(capability)`: tool contract scaffold for extract/validate/redact capabilities.
- `resolve_document_processing_flow(user_request)`: routes request to invoice, CV, or generic extraction flow.

- `list_platform_blueprints`: returns document-processing blueprint catalogs in one response.

## 2) Insurance document-reading extension

Insurance policy requests are handled as document-processing workflows with a dedicated **insurance-document-reader-agent**.

### Insurance skills

1. **insurance-policy-reading**
   - Reads policy declarations, schedules, endorsements, certificates, renewal notices, and claim forms.
   - Extracts insurer, policyholder, policy number, effective dates, limits, deductibles, premiums, exclusions, endorsements, cancellation, and renewal terms.

2. **coverage-exclusions-analysis**
   - Maps user scenarios to coverage grants, limits, exclusions, exceptions, endorsements, and unknowns.
   - Flags ambiguous clauses and recommends human review rather than making binding coverage determinations.

3. **claims-requirements-extraction**
   - Extracts notice duties, proof-of-loss requirements, evidence checklists, deadlines, contacts, and escalation paths.
   - Produces actionable claim-preparation checklists while protecting sensitive claim details.

### Insurance agent

**insurance-document-reader-agent**
- Input: extracted policy text, insurance document type, user question, optional scenario/claim details.
- Output: coverage summary, exclusions, claim requirements, missing-information prompts, confidence warnings, and human-review recommendations.
- Uses: `insurance-policy-reading`, `coverage-exclusions-analysis`, `claims-requirements-extraction`, `document-validation`, and `pii-redaction`.

### Routing examples

- “Read this insurance policy and summarize coverage” -> `insurance_policy_reading`.
- “Is water damage excluded in this policy?” -> `insurance_policy_reading` with `coverage-exclusions-analysis`.
- “What documents do I need for this claim?” -> `insurance_policy_reading` with `claims-requirements-extraction`.


## 3) CV/resume document-reading extension

CV and resume requests are handled as document-processing workflows with a dedicated **cv-reader-agent**.

### CV/resume skills

1. **cv-reading**
   - Reads CVs, resumes, academic CVs, candidate profiles, portfolios, and role-specific application documents.
   - Produces evidence-backed candidate summaries, extracted facts, strengths, missing-information notes, and review warnings.

2. **candidate-profile-extraction**
   - Extracts identity, contact channels, work history, education, certifications, projects, publications, languages, links, and skills.
   - Preserves field-level confidence, source references, and explicit “not found” markers for missing fields.

3. **experience-skills-normalization**
   - Normalizes chronology, durations, overlaps, gaps, technologies, domain keywords, and skills matrices.
   - Links skills to supporting roles, projects, certifications, or education instead of inferring unsupported competencies.

### CV/resume agent

**cv-reader-agent**
- Input: extracted CV/resume text, target role context, user question, optional language/region/compliance constraints.
- Output: candidate profile, experience timeline, skills matrix, education/certification summary, confidence warnings, chronology issues, and human-review prompts.
- Uses: `cv-reading`, `candidate-profile-extraction`, `experience-skills-normalization`, `document-validation`, and `pii-redaction`.

### Routing examples

- “Read this CV and summarize the candidate” -> `cv_reading`.
- “Extract skills from this resume” -> `cv_reading` with `experience-skills-normalization`.
- “Create a structured candidate profile from this curriculum vitae” -> `cv_reading` with `candidate-profile-extraction`.
