# MediBridge — API Guide

## 1. API base and interactive documentation

For local development, the base URL is:

```text
http://127.0.0.1:8000
```

| Resource | URL |
|---|---|
| Health check | `/api/health/` |
| Swagger UI | `/api/docs/` |
| ReDoc | `/api/redoc/` |
| OpenAPI schema | `/api/schema/` |
| Django admin | `/admin/` |

The live OpenAPI schema is authoritative for exact action routes, request/response schemas, status codes, and accepted fields. This guide summarizes the endpoint groups and workflows confirmed in the URL configuration and view/serializer excerpts shared during development.

## 2. Authentication

The API uses Simple JWT with email-based login.

### Obtain tokens

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

Use the access token as a Bearer token:

```http
Authorization: Bearer <access-token>
```

Swagger UI has an **Authorize** control for this purpose. Follow the input instructions shown by the current Swagger security scheme.

### Refresh a token

```http
POST /api/auth/token/refresh/
Content-Type: application/json
```

```json
{
  "refresh": "<refresh-token>"
}
```

### Current user

```http
GET /api/auth/me/
```

### Patient registration

```http
POST /api/auth/register/
Content-Type: application/json
```

The public registration view is intended for patient registration. Doctor and diagnostic-center staff profiles require authorized setup and verification.

### Configured token lifetimes

The settings shared during review configure a 30-minute access token and a one-day refresh token, with refresh rotation enabled.

## 3. System endpoint

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health/` | Returns API health/service/version information. |

## 4. Patient and clinical-record endpoints

Base path: `/api/medical-records/`

| Method | Path | Purpose |
|---|---|---|
| `GET`, `POST` | `/api/medical-records/relationships/` | List or create doctor–patient relationships, subject to view permissions. |
| `POST` | `/api/medical-records/relationships/{id}/accept/` | Accept a relationship. |
| `POST` | `/api/medical-records/relationships/{id}/revoke/` | Revoke a relationship. |
| `GET`, `POST` | `/api/medical-records/consultations/` | List or create consultations. |
| `GET`, `POST` | `/api/medical-records/observations/` | List or create observations. |

The API router may expose detail operations for the viewsets. Consult Swagger for the exact list/detail methods and payload schemas.

## 5. Diagnostic endpoints

Base path: `/api/diagnostics/`

### Services

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/diagnostics/services/` | Browse active diagnostic services at eligible centers. |
| `POST` | `/api/diagnostics/services/` | Create a diagnostic service where staff permissions allow it. |

### Diagnostic requests

| Method | Path | Purpose |
|---|---|---|
| `GET`, `POST` | `/api/diagnostics/requests/` | List or create diagnostic requests. |
| `POST` | `/api/diagnostics/requests/{id}/attachments/` | Upload a file to an eligible in-progress investigation. |
| `GET` | `/api/diagnostics/requests/{id}/attachments/{attachment_id}/download/` | Download an attachment after authorization. |
| `POST` | `/api/diagnostics/requests/{id}/analyze/` | Run the supported chest X-ray analysis. |
| `GET` | `/api/diagnostics/requests/{id}/analyses/` | List AI analyses for the request. |
| `POST` | `/api/diagnostics/requests/{id}/analyses/{analysis_id}/review/` | Record an authorized AI analysis review. |
| `POST` | `/api/diagnostics/requests/{id}/submit-report/` | Submit the diagnostic report. |

The request viewset also has lifecycle actions for center staff (such as accepting/starting an investigation) in the implementation history. Confirm their exact generated path and HTTP method in Swagger before calling them; do not infer action names from this summary.

### Attachment upload

The upload action uses `multipart/form-data`. The verified Swagger schema contained these writable fields:

| Field | Description |
|---|---|
| `file` | The attachment file. |
| `attachment_type` | Attachment category, such as `CLINICAL_IMAGE`. |

The request and uploader are assigned by the backend. They are not trusted as client-submitted fields. The uploader must be diagnostic staff authorized for the request's center, and the investigation must be in progress.

### AI analysis

The analyze action accepts the attachment identifier. The implementation checks that:

- The requester is authorized center staff for the diagnostic request.
- The service is a chest X-ray service supported by the current model.
- The investigation is in progress.
- The selected attachment belongs to the same request and is a clinical image.

The analysis record includes model/source references, status, pathology scores, score semantics, and review information. Scores are model outputs, not confirmed diagnoses.

### AI review and report submission

An authorized reviewer records the review status and optional notes. The report submission implementation supports an optional `ai_analysis_id`.

When supplied, the chosen analysis is scoped to the same diagnostic request and must be completed, accepted, have a recorded reviewer, and contain pathology scores. The backend adds a snapshot under `findings.ai_assistance`. Clients must not populate that reserved key themselves.

Example report body (clinical text is illustrative and must be replaced with actual clinician-reviewed content):

```json
{
  "findings": {
    "examination": "Chest X-ray",
    "clinical_observations": "Enter actual clinician-reviewed observations."
  },
  "impression": "Enter the actual clinician-authored impression.",
  "ai_analysis_id": "<accepted-analysis-uuid>"
}
```

## 6. Diagnostic report endpoints

Base path: `/api/diagnostics/reports/`

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/diagnostics/reports/` | List reports visible to the authenticated user. |
| `GET` | `/api/diagnostics/reports/{id}/` | Retrieve an authorized report. |
| `POST` | `/api/diagnostics/reports/{id}/verify/` | Verify a submitted report. |
| `POST` | `/api/diagnostics/reports/{id}/release/` | Release a verified report. |
| `GET` | `/api/diagnostics/reports/{id}/download/` | Download the released report as PDF. |

Patient report access is restricted to released reports. Doctors are restricted by ordering-doctor or active doctor–patient relationship rules. Diagnostic staff access is scoped to their active center memberships. A report preparer cannot verify their own report. The release operation requires a verified report and marks the associated diagnostic request completed.

The report PDF is distinct from the original diagnostic attachment download. The report PDF includes saved report information; the attachment endpoint returns the original uploaded image/document.

## 7. Prescription endpoints

Base path: `/api/prescriptions/`

| Method | Path | Purpose |
|---|---|---|
| `GET`, `POST` | `/api/prescriptions/` | List visible prescriptions or create a draft as an eligible doctor. |
| `GET` | `/api/prescriptions/{id}/` | Retrieve an authorized prescription. |
| `POST` | `/api/prescriptions/{id}/issue/` | Issue a draft prescription; restricted to the issuing doctor. |
| `GET` | `/api/prescriptions/{id}/download/` | Download the issued prescription as PDF. |

Prescription creation requires an approved doctor profile, an active doctor–patient relationship, and at least one medication item. A supplied consultation must belong to the same doctor and patient and meet the signed-consultation requirement. Patients are limited to their own issued prescriptions.

A medication item supports the following fields in the shared serializer:

- `medication_name`
- `generic_name`
- `strength`
- `dosage`
- `route`
- `frequency`
- `duration`
- `quantity`
- `instructions`

The exact prescription create payload is available in Swagger. Values in any sample request must be treated as illustrative, not medical advice.

## 8. Recommended demonstration sequence

1. Register or authenticate a patient.
2. Authenticate an authorized doctor and establish/accept the appropriate relationship.
3. Create a diagnostic request for a service.
4. Authenticate a staff user with active membership in the assigned center.
5. Accept/start the request using the current Swagger action routes.
6. Upload a clinical image.
7. For a chest X-ray service, run AI analysis.
8. Have a different authorized verifier review the AI analysis.
9. Submit a diagnostic report, optionally including the accepted analysis.
10. Verify the report with an authorized verifier who did not prepare it.
11. Release the report and download the report PDF as the patient.
12. Have an approved doctor create and issue a prescription, then download the prescription PDF as the patient.

Use synthetic/demo data only. Do not use example text as an actual clinical observation or treatment recommendation.

## 9. Error and authorization expectations

The API uses DRF permission and validation responses. Depending on the view/queryset design, unauthorized object access may appear as `403 Forbidden` or `404 Not Found` to avoid revealing whether an object exists. The exact response should be verified per endpoint in the automated security tests.

Do not assume that possession of a UUID grants access. Every request must pass the role, relationship, membership, and workflow-state checks implemented for that action.
