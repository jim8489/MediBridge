# MediBridge

**Healthcare Coordination & AI-Assisted Diagnostics — Django REST Framework Backend**

MediBridge is a role-aware healthcare coordination backend that connects patients, doctors, and diagnostic-center teams through structured clinical and diagnostic workflows. It provides JWT authentication, patient–doctor relationships, consultations, clinical observations, diagnostic requests, private attachment handling, independently verified reports, prescriptions, PDF generation, and human-reviewed AI-assisted chest X-ray analysis.

> **Project status:** Internship demonstration backend. The repository contains a working API implementation and automated test suite. It is not a publicly hosted clinical service, a production-certified health information system, or a clinically validated diagnostic device.

---

## 1. Project links and evaluator access

| Resource | Link / access |
|---|---|
| GitHub repository | <https://github.com/jim8489/MediBridge> |
| Project landing page | <https://jim8489.github.io/MediBridge/> |
| OpenAPI / Swagger reference | <https://jim8489.github.io/MediBridge/swagger/> |
| Interactive Swagger (local) | `http://127.0.0.1:8000/api/docs/` |
| ReDoc (local) | `http://127.0.0.1:8000/api/redoc/` |
| OpenAPI schema (local) | `http://127.0.0.1:8000/api/schema/` |
| Health check (local) | `http://127.0.0.1:8000/api/health/` |

### Important access note

MediBridge is currently delivered as a **backend/API project**. There is no publicly hosted application server and no shared online demo account. The GitHub Pages Swagger site is a static, read-only API reference; it does not connect to a live backend. To execute API requests, an evaluator can run the project locally by following the steps below.

For security, this repository does not publish reusable passwords, JWTs, database files, or private diagnostic uploads. During local setup, the evaluator creates a local administrator and local test accounts. Patient accounts can also be registered through the public patient-registration endpoint. Doctor profiles and diagnostic-center staff memberships require authorized local provisioning.

---

## 2. What has been built

MediBridge implements the backend workflows needed to coordinate clinical relationships, medical records, diagnostic services, AI-assisted analysis, report governance, and prescriptions.

### Implemented capabilities

- **Identity and authentication:** custom email-based user model, UUID identifiers, JWT access/refresh tokens, patient registration, and role-aware API permissions.
- **Patient–doctor coordination:** patient-initiated relationship requests, doctor acceptance, relationship visibility, and revocation.
- **Clinical records:** draft and signed consultations, plus patient-reported and clinician-recorded observations.
- **Diagnostic operations:** diagnostic centers, center memberships, diagnostic services, patient diagnostic requests, request acceptance/start actions, attachment upload, and authorized attachment download.
- **Report governance:** report submission, independent verification, release, authorized retrieval, and PDF download.
- **Prescription management:** structured medication items, doctor-controlled issuing, patient access to issued prescriptions, and PDF download.
- **AI-assisted decision support:** TorchXRayVision DenseNet121 inference for the supported chest X-ray workflow, persisted analysis records, human review, and accepted AI-assistance snapshots in diagnostic reports.
- **API documentation:** generated OpenAPI schema, local interactive Swagger UI, ReDoc, and static GitHub Pages Swagger reference.

The project intentionally focuses on backend APIs and workflow enforcement. It does **not** include a patient or doctor frontend dashboard, automatic report notifications, or a hosted production API.

---

## 3. User roles and access model

| Role | Main responsibilities | Access boundary |
|---|---|---|
| **Patient** | Register, request diagnostic services, initiate doctor relationships, view own clinical information, and access released reports and issued prescriptions. | Restricted to patient-owned resources and permitted workflow states. |
| **Doctor** | Work with connected patients, create/sign consultations, record observations, retrieve authorized diagnostic reports, and create/issue prescriptions. | Requires an approved doctor profile and applicable patient relationship or ordering-doctor authorization. |
| **Diagnostic staff** | Process diagnostic requests, upload attachments, perform supported AI analysis, and prepare reports. | Requires active membership in the diagnostic center associated with the request/service. |
| **Report verifier** | Independently verify and release prepared reports. | Requires authorized verifier membership. The report preparer cannot verify their own report. |
| **Administrator** | Provision accounts, profiles, centers, memberships, and permitted administrative records. | Django staff/admin privileges and endpoint-specific authorization. |

Access is determined by role **and** resource ownership, doctor–patient relationship, diagnostic-center membership, and workflow state. Knowing a UUID does not grant access to a resource.

---

## 4. Technology stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Backend framework | Django 5.2 |
| REST API | Django REST Framework |
| Authentication | Simple JWT |
| API schema | drf-spectacular / OpenAPI |
| API exploration | Swagger UI and ReDoc |
| Local database | SQLite |
| Configurable database | PostgreSQL URL support via `dj-database-url` and `psycopg` |
| AI inference | PyTorch, TorchVision, TorchXRayVision |
| Model | DenseNet121 with `densenet121-res224-all` weights |
| PDF generation | ReportLab |
| Environment configuration | `python-dotenv` and environment variables |

Pinned dependencies are listed in [`requirements.txt`](requirements.txt). The project was developed and verified locally. PostgreSQL configuration is available, but a hosted PostgreSQL deployment has not been independently validated as part of this demonstration.

---

## 5. Run MediBridge locally

### Prerequisites

- Python 3.11 recommended.
- Git.
- Internet access for dependency installation and, when needed, initial model-weight retrieval.
- Sufficient memory and disk space for the PyTorch/TorchXRayVision dependency stack.

### Step 1 — Clone the repository

```bash
git clone https://github.com/jim8489/MediBridge.git
cd MediBridge
```

### Step 2 — Create and activate a virtual environment

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Step 3 — Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The AI dependency stack is version-sensitive. Use the repository's pinned requirements when reproducing the demonstrated inference workflow. Validate any dependency changes with a fresh model-load and inference test.

### Step 4 — Configure environment variables

Create a local environment file:

```bash
cp .env.example .env
```

Review the values in `.env` and set a unique, high-entropy `SECRET_KEY`. Keep `.env` private and never commit it. The example configuration is intended for local development only. Do not use development settings for a hosted deployment.

### Step 5 — Initialize the database

```bash
python manage.py migrate
python manage.py createsuperuser
```

The default local database is SQLite. PostgreSQL connection URL configuration is also present, but the evaluator should configure and validate a PostgreSQL environment separately if choosing that option.

### Step 6 — Provision evaluator accounts and domain records

Start with the local Django administrator created above. Use Django admin or the project's authorized local provisioning process to create the records required for each role:

1. **Patient:** register using `POST /api/auth/register/` or create a local patient account. The registration endpoint is intended for patient registration.
2. **Doctor:** create a doctor user and profile, and ensure the profile is approved before testing doctor-specific operations.
3. **Diagnostic center:** create a diagnostic-center record and the required diagnostic service.
4. **Diagnostic staff:** create staff users and active center memberships. Assign the appropriate operational membership/permissions for request processing and report verification.

A doctor needs an applicable active patient–doctor relationship for relationship-dependent clinical operations. Diagnostic staff must belong to the center associated with the request/service. These relationships and memberships are part of the authorization model, not optional display metadata.

Use synthetic identities and data. Do not use real patient records or publish local passwords, JWTs, or private uploads.

### Step 7 — Start the API server

```bash
python manage.py runserver
```

Open the interactive API documentation:

- Swagger UI: <http://127.0.0.1:8000/api/docs/>
- ReDoc: <http://127.0.0.1:8000/api/redoc/>
- Health check: <http://127.0.0.1:8000/api/health/>

### Step 8 — Authenticate in Swagger

1. Open `POST /api/auth/token/`.
2. Submit the email and password for one of the local test accounts.
3. Copy the returned `access` token.
4. Select **Authorize** in Swagger and provide the token as a Bearer token.
5. Execute endpoints available to that account's role.
6. When changing roles, obtain and authorize with that role's own token.

Do not share access or refresh tokens. Exact request fields and response schemas are defined in the generated OpenAPI document and local Swagger UI.

For expanded environment and reproducibility guidance, see [`docs/SETUP.md`](docs/SETUP.md).

---

## 6. How the key workflows work

### A. Patient–doctor relationship and clinical records

1. A patient creates a relationship request for an approved doctor.
2. The requested doctor accepts the pending relationship.
3. The connected doctor creates and signs a consultation.
4. The doctor records clinical observations; the patient can also create supported patient-reported observations for their own record.
5. The patient or connected doctor can revoke the relationship under the endpoint's authorization rules.

Key endpoints:

```text
GET/POST  /api/medical-records/relationships/
POST      /api/medical-records/relationships/{id}/accept/
POST      /api/medical-records/relationships/{id}/revoke/
GET/POST  /api/medical-records/consultations/
GET       /api/medical-records/consultations/{id}/
POST      /api/medical-records/consultations/{id}/sign/
GET/POST  /api/medical-records/observations/
GET       /api/medical-records/observations/{id}/
```

### B. Diagnostic request, AI analysis, and report release

1. A patient or eligible clinician creates a diagnostic request for an available service.
2. Authorized staff at the relevant diagnostic center accept and start the request.
3. Center staff upload an eligible clinical attachment. Attachments are stored privately and downloaded through an authorization-checked endpoint.
4. For the supported chest X-ray service, eligible staff can run the AI inference endpoint.
5. An authorized reviewer reviews the completed AI analysis. The report preparer and verifier must be different users.
6. Center staff submit the diagnostic report and may link an accepted AI analysis.
7. An authorized verifier verifies the submitted report; an authorized user then releases it.
8. The request is completed. The patient can access their released report and download its PDF. An authorized doctor can retrieve reports permitted by the ordering-doctor or active-relationship access rules.

Key endpoints:

```text
GET/POST  /api/diagnostics/requests/
POST      /api/diagnostics/requests/{id}/accept/
POST      /api/diagnostics/requests/{id}/start/
POST      /api/diagnostics/requests/{id}/attachments/
GET       /api/diagnostics/requests/{id}/attachments/{attachment_id}/download/
POST      /api/diagnostics/requests/{id}/analyze/
GET       /api/diagnostics/requests/{id}/analyses/
POST      /api/diagnostics/requests/{id}/analyses/{analysis_id}/review/
POST      /api/diagnostics/requests/{id}/submit-report/
GET       /api/diagnostics/reports/
GET       /api/diagnostics/reports/{id}/
POST      /api/diagnostics/reports/{id}/verify/
POST      /api/diagnostics/reports/{id}/release/
GET       /api/diagnostics/reports/{id}/download/
```

### C. How a doctor views a patient's diagnostic report

There is no separate frontend dashboard in this backend. An authorized doctor retrieves reports through the API:

1. Authenticate as the doctor and obtain a JWT access token.
2. Call `GET /api/diagnostics/reports/` to list reports visible to that doctor.
3. Call `GET /api/diagnostics/reports/{id}/` to inspect an authorized report.
4. Call `GET /api/diagnostics/reports/{id}/download/` to download the report PDF.

The API enforces the relevant report-access rules. A future frontend can consume these endpoints to present a report list, details, and download action without changing the backend workflow.

### D. Prescription workflow

1. An eligible doctor with an active patient relationship creates a draft prescription.
2. The doctor adds one or more structured medication items and instructions.
3. The issuing doctor issues the prescription.
4. The patient can retrieve their own issued prescription and download its PDF. Other patients cannot access it.

Key endpoints:

```text
GET/POST  /api/prescriptions/
GET       /api/prescriptions/{id}/
POST      /api/prescriptions/{id}/issue/
GET       /api/prescriptions/{id}/download/
```

Exact request fields and accepted choices are available in Swagger. Medication examples are for API demonstration only and are not medical advice.

---

## 7. AI model scope and clinical limitations

The current AI integration uses TorchXRayVision DenseNet121 with `densenet121-res224-all` weights for the supported chest X-ray workflow. It records the selected model, source attachment, diagnostic request, submitter, analysis status, pathology scores, score semantics, and human-review information.

Important limitations:

- The model outputs are scores, **not calibrated probabilities, confirmed findings, or diagnoses**.
- An authorized human reviewer must accept an analysis before it can be included in a diagnostic report.
- The model is intended only for the supported chest X-ray workflow. It is not intended for diabetic-foot-ulcer photographs, PDFs, or unrelated imaging modalities.
- The integration is an engineering demonstration. It has not been clinically validated or approved as a regulated diagnostic device.

---

## 8. Security and data-handling approach

Implemented controls include:

- JWT authentication and role-aware API permissions.
- Patient ownership and doctor–patient relationship checks.
- Diagnostic-center membership checks.
- Lifecycle restrictions for reports and prescriptions.
- Independent report verification; the report preparer cannot verify their own report.
- Supported file validation and private diagnostic attachment storage.
- Authorization checks before retrieving reports, attachments, and PDF files.

This implementation has not undergone a formal penetration test, independent security audit, privacy/regulatory review, or production deployment assessment. Before any hosted deployment, configure `DEBUG=False`, a unique secret key, strict allowed hosts, HTTPS, secure cookies/headers, protected database and file storage, backups, monitoring, rate limiting/abuse controls, audit logging, and appropriate legal, privacy, and clinical reviews.

The `PatientConsent` model exists, but a separate granular consent-management API is not currently exposed. Relationship acceptance should not be represented as a complete consent-management system.

---

## 9. Automated tests and verification

The latest reported local verification completed **27 automated tests successfully**:

| Test area | Tests passed |
|---|---:|
| Account registration | 3 |
| Diagnostic authorization | 10 |
| Patient–doctor and medical-record workflows | 11 |
| AI inference validation | 3 |
| **Total** | **27 / 27** |

The tests cover registration constraints, AI input/score validation, report ownership, released-report visibility, cross-patient prescription restrictions, diagnostic-center isolation, report-preparer/verifier separation, relationship operations, consultation signing/access, observation authorization, and authentication requirements.

The AI unit tests use controlled test doubles for predictable inference validation. The complete real-model diagnostic workflow was also manually exercised locally: an X-ray analysis with 18 pathology scores was accepted by a human reviewer, included in a released report, and the report PDF was downloaded successfully. Prescription PDF download was also manually verified after correcting the PDF renderer configuration.

### Reproduce the checks

```bash
python manage.py check
python -m compileall accounts patients diagnostics prescriptions organizations config
python manage.py test -v 2
python manage.py spectacular --file schema.yml --validate
```

Latest reported results:

- `python manage.py test -v 2`: **27 tests passed**.
- Django system check during the test run: **no issues reported**.
- OpenAPI generation: **0 errors; 24 warnings across 10 unique warning categories**.

The remaining schema warnings concern serializer method return-type hints and path-parameter type inference. They do not prevent schema generation, but remain documentation-quality cleanup items. After regenerating `schema.yml`, update the static Swagger schema with:

```bash
cp schema.yml docs/swagger/openapi.yml
```

---

## 10. Repository structure

```text
MediBridge/
├── accounts/          # Custom user, profiles, registration, JWT APIs
├── organizations/     # Diagnostic centers and staff memberships
├── patients/          # Relationships, consultations, observations
├── diagnostics/       # Services, requests, attachments, reports, AI analyses
├── prescriptions/     # Prescriptions, medication items, prescription PDFs
├── config/            # Django settings, URL routing, renderers
├── docs/              # Architecture, setup, API and security documentation
├── docs/swagger/      # Static OpenAPI document and Swagger UI
├── samples/           # Demonstration sample assets
├── manage.py
├── requirements.txt
└── .env.example
```

---

## 11. Documentation index

- [Architecture](docs/ARCHITECTURE.md) — domain structure, responsibilities, and workflow design.
- [Setup and Reproducibility](docs/SETUP.md) — environment configuration, installation, AI runtime, and verification.
- [API Guide](docs/API_GUIDE.md) — endpoint groups, request workflows, and authorization expectations.
- [Security and Verification](docs/SECURITY_AND_VERIFICATION.md) — access controls, test evidence, and known boundaries.
- [Static Swagger UI](https://jim8489.github.io/MediBridge/swagger/) — read-only OpenAPI reference.

---

## 12. Evaluation notes

For a focused evaluation, the recommended walkthrough is:

1. Inspect the application structure and user/role model.
2. Run the project locally and open interactive Swagger.
3. Authenticate as a patient and demonstrate a patient–doctor relationship request.
4. Authenticate as the requested doctor and accept the relationship; create and sign a consultation.
5. Demonstrate the diagnostic request lifecycle, attachment upload, supported AI analysis, human review, report verification, and release.
6. Retrieve the released report as the patient and as an authorized doctor; download the PDF.
7. Demonstrate prescription creation, issuance, patient retrieval, and PDF download.
8. Run the automated test suite and inspect the OpenAPI schema.

The project is submitted as a backend engineering demonstration. Its purpose is to show API design, domain modeling, authorization, workflow enforcement, AI integration, PDF generation, automated testing, and technical documentation—not to claim that a complete clinical product is deployed.
