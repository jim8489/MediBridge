# MediBridge — Security and Verification Status

## 1. Purpose

This document distinguishes implemented safeguards and observed verification results from tests and production controls that remain outstanding. It is intended to keep project demonstrations accurate and avoid overstating security assurance.

## 2. Safeguards visible in the shared implementation

### Authentication and identity

- Custom user model with email-based authentication.
- UUID identifiers in core models.
- JWT access/refresh authentication.
- Patient-only public registration flow as described in the existing README and account URL configuration.

### Resource authorization

- Patient report queries are restricted to the authenticated patient's own released reports.
- Patient prescription queries are restricted to the authenticated patient's own issued prescriptions.
- Doctor report access checks ordering-doctor or active doctor–patient relationship conditions.
- Prescription creation requires an approved doctor profile and active doctor–patient relationship.
- Diagnostic staff operations check active membership in the center associated with the request/service.
- Attachment download checks patient ownership/report release, doctor authorization, or center membership according to the caller role.

### Workflow controls

- Diagnostic reports move through submitted, verified, and released states.
- A report must be verified before release.
- The person who prepared a report cannot verify it.
- Releasing a report marks the linked diagnostic request completed.
- Only the issuing doctor can issue their draft prescription.
- Patients are shown issued prescriptions, not drafts.

### File handling

- Diagnostic attachments use private storage in the implementation.
- The download endpoint streams the file after authorization instead of exposing a public storage URL.
- File validation checks permitted file characteristics, including file signature validation in the shared serializer/model implementation.

### AI provenance and human review

- AI analyses record the model, source attachment, request, submitter, output/status, score semantics, and review information.
- The report-submission logic validates that a selected AI analysis belongs to the same request, completed successfully, was accepted, has a recorded reviewer, and contains pathology scores.
- AI information is stored separately from clinician-authored findings and impression.
- The model is restricted to the supported chest X-ray workflow.

## 3. Local validation results reported on 6 November 2026

The user shared the following terminal results:

| Command | Observed result |
|---|---|
| `python manage.py check` | No system-check issues. |
| `python -m compileall diagnostics prescriptions` | Completed. |
| `python manage.py spectacular --file schema.yml --validate` | Zero errors; 24 warnings (10 unique categories). |
| `python manage.py test` | Six tests found; all six passed. |

OpenAPI warnings included unresolved serializer method return type hints and path-parameter type inference for UUID-like identifiers. These were warnings, not schema-generation errors, but should be cleaned up before treating the schema as final.

The existing AI analysis originally had 18 scores in `model_output` but an empty `pathology_scores` field. A one-time recovery command copied the existing 18 scores into `pathology_scores`; the user confirmed the recovery output showed 18 stored scores and `ACCEPTED` review status.

## 4. Tests still required

The full automated security regression suite had not yet been implemented at the last reported milestone. Recommended cases include:

| Scenario | Required expectation |
|---|---|
| Patient A requests Patient B's report | Denied; no data leakage. |
| Patient A downloads Patient B's prescription | Denied. |
| Unrelated doctor requests a patient's report | Denied. |
| Authorized doctor requests an associated patient's report | Allowed. |
| Staff from Center A accesses Center B's request | Denied. |
| Patient downloads an unreleased diagnostic report | Denied. |
| Report preparer attempts self-verification | Denied. |
| Different authorized verifier verifies the report | Allowed. |
| Unapproved doctor creates a prescription | Denied. |
| Unauthenticated or unauthorized user uploads an attachment | Denied. |
| Patient downloads own released report | Allowed. |
| Patient downloads own issued prescription | Allowed. |

These should be Django REST Framework API tests using test database fixtures, authenticated clients, and the actual route actions. Tests should cover both denial and legitimate access.

## 5. Additional production controls not established by current evidence

Do not claim these controls as completed unless separately implemented and tested:

- Formal penetration test or independent security audit.
- Encryption-at-rest configuration for database and file storage.
- Complete audit-event logging for all sensitive record access and changes.
- Rate limiting and abuse protection.
- Backup/restore and disaster-recovery exercises.
- Production HTTPS and secure cookie/header configuration.
- Centralized secret management.
- Malware scanning/quarantine for uploaded files.
- Formal privacy impact assessment or regulatory compliance certification.
- Clinical validation or regulatory approval of the AI model.
- Production monitoring, alerting, and incident-response procedures.

## 6. Safe demonstration guidance

- Use synthetic patient data and demo credentials.
- Never share `.env`, local database files, or private attachments.
- Avoid displaying access tokens or passwords in screenshots/videos.
- Explain AI scores as decision-support outputs, not a diagnosis.
- Show the independent report-verification workflow.
- Demonstrate at least one denied cross-patient or cross-center access attempt after the automated security tests exist.
