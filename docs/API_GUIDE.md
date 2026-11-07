# MediBridge — API Guide

This guide summarizes the API surface and the principal role-based workflows. The generated OpenAPI document and the local interactive Swagger UI are authoritative for exact request fields, serializer constraints, response schemas, and status codes.

## 1. API base and documentation

Local development base URL:

```text
http://127.0.0.1:8000
```

| Resource | Path |
|---|---|
| Health check | `/api/health/` |
| Swagger UI | `/api/docs/` |
| ReDoc | `/api/redoc/` |
| OpenAPI schema | `/api/schema/` |
| Django admin | `/admin/` |

The public GitHub Pages Swagger reference is static and read-only. It does not connect to a public API server. Use the local Swagger UI to execute requests against a running development instance.

## 2. Authentication

The API uses email-based authentication with Simple JWT.

### Obtain access and refresh tokens

```http
POST /api/auth/token/
Content-Type: application/json
```

```json
{
  "email": "patient@example.com",
  "password": "your-local-test-password"
}
```

Use the returned access token as a Bearer token:

```http
Authorization: Bearer <access-token>
```

Swagger UI provides an **Authorize** control. Do not paste access or refresh tokens into source code, screenshots, issue reports, or public documentation.

### Refresh an access token

```http
POST /api/auth/token/refresh/
Content-Type: application/json
```

```json
{
  "refresh": "<refresh-token>"
}
```

### Current user and registration

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/auth/me/` | Retrieve the authenticated user's current profile/role information. |
| `POST` | `/api/auth/register/` | Public patient registration. |
| `POST` | `/api/auth/token/` | Obtain JWT tokens. |
| `POST` | `/api/auth/token/refresh/` | Refresh an access token. |

Public registration is intended for patients. Doctor profiles and diagnostic-center staff memberships require authorized provisioning/verification.

## 3. Health endpoint

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health/` | Return API health/service/version information. |

## 4. Patient–doctor relationship and clinical-record APIs

Base path: `/api/medical-records/`

### Relationships

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/medical-records/relationships/` | List relationships visible to the authenticated user. |
| `POST` | `/api/medical-records/relationships/` | Create a patient-initiated doctor relationship request. |
| `POST` | `/api/medical-records/relationships/{id}/accept/` | Allow the requested doctor to accept a pending relationship. |
| `POST` | `/api/medical-records/relationships/{id}/revoke/` | Revoke a relationship under the endpoint's patient/doctor authorization rules. |

A patient initiates the relationship request. The requested doctor accepts it. The active relationship is used by downstream clinical operations and doctor access rules. A relationship request is not the same as a separate granular consent-management API.

### Consultations

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/medical-records/consultations/` | List consultations visible to the authenticated user. |
| `POST` | `/api/medical-records/consultations/` | Create a consultation under the applicable doctor/patient rules. |
| `GET` | `/api/medical-records/consultations/{id}/` | Retrieve an authorized consultation. |
| `POST` | `/api/medical-records/consultations/{id}/sign/` | Sign a consultation through the authorized doctor action. |

The consultation workflow supports draft and signed records. Patients are intended to access signed consultations; doctors must satisfy the relevant relationship and ownership checks.

### Clinical observations

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/medical-records/observations/` | List observations visible to the authenticated user. |
| `POST` | `/api/medical-records/observations/` | Create an observation under patient/doctor authorization rules. |
| `GET` | `/api/medical-records/observations/{id}/` | Retrieve an authorized observation. |

The implementation supports patient-reported and clinician-recorded observations. Doctor-recorded observations require the applicable active relationship; the patient can create supported observations for their own record. Diagnostic staff do not receive clinical observation records through this endpoint.

## 5. Diagnostic-center service and request APIs

Base path: `/api/diagnostics/`

### Diagnostic services

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/diagnostics/services/` | List diagnostic services available under the service visibility rules. |
| `POST` | `/api/diagnostics/services/` | Create a diagnostic service when the caller has the required center permissions. |
| `GET` | `/api/diagnostics/services/{id}/` | Retrieve a service visible to the caller. |

### Diagnostic requests and actions

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/diagnostics/requests/` | List diagnostic requests visible to the authenticated user. |
| `POST` | `/api/diagnostics/requests/` | Create a diagnostic request when permitted. |
| `GET` | `/api/diagnostics/requests/{id}/` | Retrieve an authorized request. |
| `POST` | `/api/diagnostics/requests/{id}/accept/` | Accept a request through an authorized center-staff membership. |
| `POST` | `/api/diagnostics/requests/{id}/start/` | Start the investigation through an authorized center-staff membership. |
| `POST` | `/api/diagnostics/requests/{id}/submit-report/` | Submit the report for the request. |

### Attachments

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/diagnostics/requests/{id}/attachments/` | Upload an eligible attachment to the request. |
| `GET` | `/api/diagnostics/requests/{id}/attachments/{attachment_id}/download/` | Download an attachment after authorization. |

The upload action uses `multipart/form-data`. The request and uploader are assigned/validated by the backend; the caller must be authorized center staff for the request's center, and the request must be in the appropriate workflow state. Upload validation checks supported file characteristics. Attachments are stored privately and streamed after authorization rather than exposed through a public storage URL.

## 6. AI analysis and human review

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/diagnostics/requests/{id}/analyze/` | Run supported chest X-ray inference for an eligible attachment. |
| `GET` | `/api/diagnostics/requests/{id}/analyses/` | List analysis records associated with a request. |
| `POST` | `/api/diagnostics/requests/{id}/analyses/{analysis_id}/review/` | Record an authorized review of an AI analysis. |

The current integration uses TorchXRayVision DenseNet121 with `densenet121-res224-all` weights. The analysis action is restricted to the supported chest X-ray service and an eligible clinical-image attachment belonging to the same request. The analysis record retains model/source references, submitter, status, pathology scores, score semantics, and review metadata.

**Interpretation boundary:** the scores are model outputs, not calibrated probabilities or diagnoses. A human reviewer must accept an analysis before it can be attached to the report.

### Report-submission integration

The report submission action supports an optional `ai_analysis_id`. When provided, the selected analysis must belong to the same request, be completed, have an accepted review and recorded reviewer, and contain pathology scores. The backend snapshots the model output and review information under `findings.ai_assistance`; clients should not construct or submit that reserved snapshot themselves.

Illustrative request body (clinical content must be supplied by an appropriately qualified clinician and is not medical advice):

```json
{
  "findings": {
    "examination": "Chest X-ray",
    "clinical_observations": "Enter clinician-reviewed observations."
  },
  "impression": "Enter the clinician-authored impression.",
  "ai_analysis_id": "<accepted-analysis-uuid>"
}
```

## 7. Diagnostic report APIs

Base path: `/api/diagnostics/reports/`

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/diagnostics/reports/` | List reports visible to the authenticated user. |
| `GET` | `/api/diagnostics/reports/{id}/` | Retrieve an authorized report. |
| `POST` | `/api/diagnostics/reports/{id}/verify/` | Verify a submitted report as an authorized verifier. |
| `POST` | `/api/diagnostics/reports/{id}/release/` | Release a verified report. |
| `GET` | `/api/diagnostics/reports/{id}/download/` | Download the report as a PDF. |

The report lifecycle is `SUBMITTED` → `VERIFIED` → `RELEASED`. A report must be verified before release, and the report preparer cannot verify their own report. Release completes the associated diagnostic request.

Patient access is limited to their own released reports. Doctor access is based on the ordering-doctor or active doctor–patient relationship rules. Center staff access is scoped to the relevant diagnostic-center membership.

### How a doctor retrieves a patient report

There is no separate dashboard in this backend. An authorized doctor retrieves available reports through the API:

1. Authenticate and obtain a JWT access token.
2. Call `GET /api/diagnostics/reports/` to list reports visible to that doctor.
3. Call `GET /api/diagnostics/reports/{id}/` to inspect an authorized report.
4. Call `GET /api/diagnostics/reports/{id}/download/` to obtain the PDF.

The backend applies the report queryset/object authorization rules. A future frontend can call these endpoints to present the report list, details, and download action without changing the backend workflow.

The report PDF is distinct from the original attachment download. The report PDF represents the saved report; the attachment endpoint returns the original uploaded file.

## 8. Prescription APIs

Base path: `/api/prescriptions/`

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/prescriptions/` | List prescriptions visible to the authenticated user. |
| `POST` | `/api/prescriptions/` | Create a draft prescription as an eligible doctor. |
| `GET` | `/api/prescriptions/{id}/` | Retrieve an authorized prescription. |
| `POST` | `/api/prescriptions/{id}/issue/` | Issue a draft prescription; restricted to its issuing doctor. |
| `GET` | `/api/prescriptions/{id}/download/` | Download an issued prescription as a PDF. |

Prescription creation requires an approved doctor profile, an active patient relationship, and at least one medication item. If a consultation is supplied, it must belong to the same patient and doctor and meet the signed-consultation requirement. Patients are restricted to their own issued prescriptions; draft prescriptions are not available to patients.

Structured medication items support fields including medication name, generic name, strength, dosage, route, frequency, duration, quantity, and instructions. Consult Swagger for the current serializer's exact required fields and accepted values. Example medication content is illustrative and must not be treated as clinical guidance.

## 9. Authentication and authorization expectations

Most business endpoints require JWT authentication. Access is additionally limited by role, resource ownership, an active doctor–patient relationship, diagnostic-center membership, and resource lifecycle state.

Depending on the view and queryset design, unauthorized object access may return `403 Forbidden` or `404 Not Found`. A `404` can be intentional to avoid disclosing the existence of another user's resource. A UUID is an identifier, not an access credential.

## 10. Consent API boundary

A `PatientConsent` model exists in the project, but the current OpenAPI route inventory does not expose a separate consent-management endpoint. Do not describe the current API as providing a complete consent grant/revoke/history service. Relationship acceptance and revocation are implemented separately from any future granular consent-management API.

## 11. Recommended demonstration sequence

1. Authenticate a patient and retrieve the current user profile.
2. Create a relationship request to an approved doctor.
3. Authenticate as that doctor and accept the relationship.
4. Create a consultation, sign it, and retrieve it as the patient.
5. Create a patient or clinician observation and check access from another patient account.
6. Create a diagnostic request and authenticate a staff user with active membership in its center.
7. Accept and start the request; upload an eligible clinical image.
8. For a supported chest X-ray, run AI inference and review the analysis with an authorized reviewer.
9. Submit, independently verify, and release the diagnostic report.
10. Retrieve the released report as the patient and, where authorized, as the doctor; download the report PDF.
11. Create and issue a prescription as the doctor; retrieve and download it as the patient.
12. Test cross-patient and cross-center restrictions with separate demo accounts.

Use synthetic or properly licensed data only. Do not expose JWT tokens, credentials, private attachments, or identifiable health information during a demonstration.
