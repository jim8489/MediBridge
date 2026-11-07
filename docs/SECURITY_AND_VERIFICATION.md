# MediBridge — Security and Verification

## 1. Purpose and assurance boundary

This document records the security controls represented in the current implementation and the verification results reported during local development. It distinguishes automated regression coverage and manual API checks from security, privacy, operational, and clinical assurances that have **not** been established.

MediBridge is an internship demonstration backend. Passing its current test suite does not constitute a formal security audit, penetration test, privacy certification, production-readiness assessment, or clinical validation.

## 2. Implemented security and workflow controls

### Authentication and identity

- Custom email-based user model with UUID identifiers in core domain records.
- JWT access/refresh authentication.
- Public registration is intended for patient accounts; elevated doctor and diagnostic-center staff roles require authorized provisioning/verification.
- Authenticated current-user endpoint for retrieving the caller's profile/role information.

### Resource-level authorization

- Patient report querysets are restricted to the authenticated patient's own released reports.
- Patient prescription querysets are restricted to the authenticated patient's own issued prescriptions.
- Doctor report access is constrained by the ordering-doctor or active doctor–patient relationship rules.
- Prescription creation requires an approved doctor profile and an active relationship with the patient.
- Consultation and observation access/creation is constrained by the relevant patient, doctor, ownership, and relationship rules.
- Diagnostic staff operations require active membership in the diagnostic center associated with the service/request.
- Attachment and PDF download actions check authorization before returning file content.
- Unauthenticated requests to protected medical-record and report endpoints are rejected.

### Workflow integrity

- Patient–doctor relationships have request/accept/revoke operations; the requested doctor accepts the pending relationship.
- Consultation records support a draft/signing lifecycle.
- Observations support patient-reported and clinician-recorded sources, with role-specific access.
- Diagnostic report states progress through submitted, verified, and released states.
- A report must be verified before release.
- The report preparer cannot verify their own report.
- Releasing a report marks the associated diagnostic request completed.
- Only the issuing doctor can issue their draft prescription.
- Patients are restricted to issued prescriptions, not drafts.

### File handling and PDF delivery

- Diagnostic attachments use private storage.
- Upload validation checks supported file characteristics, including extension and file-signature validation in the implementation.
- Attachment downloads stream file contents after authorization rather than exposing a public storage URL.
- Diagnostic reports and prescriptions are generated as PDFs from persisted records using ReportLab.
- PDF download actions declare a PDF renderer so clients requesting `Accept: application/pdf` can negotiate the response correctly.

### AI traceability and human review

- AI analysis records retain the diagnostic request, source attachment, registered model, submitting user, output/status, score semantics, and review information.
- Report submission validates that a referenced analysis belongs to the same request, completed successfully, has an accepted review and recorded reviewer, and contains pathology scores.
- The report stores an AI-assistance snapshot separately from clinician-entered findings and impression.
- The current model integration is limited to the supported chest X-ray workflow.
- AI scores are model outputs, not calibrated probabilities or confirmed diagnoses.

## 3. Automated test coverage

The latest reported command was:

```bash
python manage.py test -v 2
```

**Result: 27 tests ran and all 27 passed.** The test runner also reported no Django system-check issues.

| Test module | Tests | Coverage represented |
|---|---:|---|
| `accounts.tests` | 3 | Patient registration, password-mismatch rejection, and prevention of role escalation through public registration. |
| `diagnostics.test_api_security` | 10 | Patient report ownership, report release restrictions, authorized doctor report access, cross-patient prescription denial, own prescription download, cross-center staff isolation, report self-verification denial, and unauthenticated report access. |
| `patients.test_api_workflows` | 11 | Relationship request/accept/revoke, unauthorized relationship actions, consultation create/sign/read access, relationship requirements, observation ownership and role restrictions, and authentication requirements. |
| `diagnostics.test_ai_inference` | 3 | Rejection of document attachments, rejection of non-finite inference scores, and return of named pathology scores. |
| **Total** | **27** | **All tests passed in the reported local run.** |

These tests run against Django's test database and exercise API endpoints or inference-service behavior using test fixtures. They do not test every endpoint, every possible role combination, external deployment configuration, or every failure mode.

## 4. Manual API verification reported

The following end-to-end checks were also reported during local Swagger/API testing:

- The diagnostic request progressed through the processing and report lifecycle.
- A report was released and its linked diagnostic request was completed.
- The released report included an `ai_assistance` snapshot containing **18 pathology scores**.
- The AI assistance review status was `ACCEPTED`, with a reviewer recorded.
- The authorized patient could download the diagnostic report PDF.
- Cross-patient report download attempts were denied, and unauthenticated report access was rejected.
- Prescription PDF download initially returned `406 Not Acceptable`; the prescription action was corrected to use the configured PDF renderer, after which the user confirmed the download worked.

These are developer-reported manual verification results, not a separate automated end-to-end test suite. They demonstrate the tested local workflow and should not be generalized into a claim that every API action has been manually exercised.

## 5. OpenAPI/schema validation

The latest reported schema command was:

```bash
python manage.py spectacular --file schema.yml --validate
cp schema.yml docs/swagger/openapi.yml
```

Observed result:

| Metric | Result |
|---|---:|
| Schema generation errors | **0** |
| Schema generation warnings | **24** |
| Unique warning categories | **10** |

Warnings include unresolved return-type hints for `get_patient_profile` and `get_doctor_profile` in the current-user serializer and path-parameter type inference for UUID-like identifiers in diagnostic, consultation, observation, and prescription viewsets. The schema is generated successfully, but these warnings remain documentation-quality issues to address.

## 6. Known implementation boundaries

- A `PatientConsent` model exists, but the current API schema does not expose a separate consent-management endpoint.
- No patient/doctor frontend dashboard or automatic report-notification service is included. Authorized doctors retrieve reports through the report list, detail, and download endpoints.
- The public GitHub Pages Swagger site is a static API reference, not a live connection to a deployed backend.
- The current AI model is a chest X-ray decision-support integration only. It has not been clinically validated or approved for autonomous diagnosis.
- Manual API testing and automated regression tests cover important workflows but are not exhaustive.

## 7. Controls not established by current evidence

Do not claim the following controls as completed unless they are implemented and separately verified:

- Independent penetration test, security audit, or threat-model review.
- Comprehensive audit-event logging for all sensitive record reads and changes.
- Configured rate limiting, abuse protection, and account lockout controls.
- Encryption-at-rest configuration for database and file storage.
- Production HTTPS, secure cookie/header configuration, and hardened application server deployment.
- Centralized production secret management and key rotation.
- Malware scanning/quarantine for uploaded files.
- Tested backup/restore and disaster-recovery procedures.
- Centralized monitoring, alerting, incident response, and operational runbooks.
- Formal privacy impact assessment, legal/regulatory compliance certification, or data-processing agreements.
- Clinical evaluation, clinical validation, or regulatory approval of the AI model or product.

## 8. Safe demonstration guidance

- Use synthetic patient identities and non-identifiable demonstration data.
- Never show `.env` contents, passwords, access/refresh tokens, or private file-storage paths in screenshots or videos.
- Use separate patient accounts to demonstrate cross-patient access restrictions.
- Use separate diagnostic staff accounts/center memberships to demonstrate center isolation.
- Show that report preparation and verification are performed by different users.
- Explain that AI scores are decision-support outputs and require human interpretation; do not present them as diagnoses.
- Do not use the demonstration model with DFU photographs, PDFs, or unsupported modalities.
