# MediBridge

**Healthcare Coordination & AI-Assisted Diagnostics — Django REST Framework Backend**

MediBridge is a role-aware healthcare coordination backend that connects patients, doctors, and diagnostic-center teams through a structured set of clinical and diagnostic workflows. It provides JWT-based authentication, patient–doctor relationships, consultations, clinical observations, diagnostic requests, secure attachment handling, independently verified reports, prescriptions, PDF generation, and human-reviewed AI-assisted chest X-ray analysis.

> **Project classification:** Internship demonstration backend. The repository contains a working API implementation and an automated test suite. It is not a deployed clinical service, a production-certified health information system, or a clinically validated diagnostic device.

| Project resource | Link |
|---|---|
| GitHub repository | [github.com/jim8489/MediBridge](https://github.com/jim8489/MediBridge) |
| Project landing page | [GitHub Pages](https://jim8489.github.io/MediBridge/) |
| OpenAPI / Swagger reference | [Static Swagger documentation](https://jim8489.github.io/MediBridge/swagger/) |
| Local interactive Swagger | `http://127.0.0.1:8000/api/docs/` |

The GitHub Pages Swagger site is a static, read-only API reference. It does not connect to a deployed MediBridge backend. Interactive requests are available when the project is run locally.

## Product scope

MediBridge is designed around distinct responsibilities and controlled transitions between the patient, clinician, and diagnostic-center workflows.

### Core capabilities

- **Identity and access:** custom email-based user model, UUID identifiers, JWT access/refresh authentication, patient registration, and role-aware API permissions.
- **Patient–doctor coordination:** relationship requests, doctor acceptance, revocation, and access constrained by the relationship state.
- **Clinical records:** consultations with a draft/signing lifecycle and patient- or clinician-recorded observations.
- **Diagnostic operations:** diagnostic-center/service records, patient diagnostic requests, staff acceptance and start actions, attachment upload/download, and request lifecycle management.
- **Report governance:** report submission, independent verification, release, authorized retrieval, and PDF download.
- **Prescription management:** structured prescription items, doctor-controlled issue workflow, patient access to issued prescriptions, and PDF download.
- **AI-assisted decision support:** registered TorchXRayVision DenseNet121 inference for supported chest X-ray requests, persisted analysis provenance, human review, and an AI-assistance snapshot in the released report.
- **API documentation:** generated OpenAPI schema, local Swagger UI, ReDoc, and a static GitHub Pages Swagger reference.

## User roles

| Role | Main responsibilities | Important access condition |
|---|---|---|
| Patient | Maintain their profile, request diagnostic services, view their clinical information, and access released reports and issued prescriptions. | Patient-owned resources and workflow state restrict access. |
| Doctor | Work with connected patients, create/sign consultations, record clinical observations, review authorized reports, and create/issue prescriptions. | Approved doctor profile and applicable active patient relationship. |
| Diagnostic staff | Process requests assigned to their diagnostic center, upload permitted attachments, run supported AI analysis, and prepare reports. | Active membership in the center associated with the request/service. |
| Report verifier | Independently verify and release prepared diagnostic reports. | Authorized verifier membership; the report preparer cannot verify their own report. |
| Administrator | Perform permitted administrative and account-management tasks. | Django staff/admin privileges and endpoint-specific authorization. |

Access is determined by the user's role **and** the relevant patient relationship, diagnostic-center membership, resource ownership, and workflow state. A role label or knowledge of a UUID does not by itself grant access.

## Technology stack

| Layer | Technology |
|---|---|
| Language/runtime | Python 3.11 (3.11.3 used in local development) |
| Web framework | Django 5.2 |
| REST API | Django REST Framework |
| Authentication | Simple JWT |
| API schema/documentation | drf-spectacular, OpenAPI, Swagger UI, ReDoc |
| Local database | SQLite |
| Configurable database backend | PostgreSQL URL configuration using `dj-database-url` and `psycopg` |
| AI inference | PyTorch, TorchVision, TorchXRayVision |
| Model | DenseNet121, `densenet121-res224-all` weights |
| PDF generation | ReportLab |
| Environment configuration | `python-dotenv` and environment variables |

Pinned dependency versions are maintained in [`requirements.txt`](requirements.txt). The application was developed and tested locally; PostgreSQL configuration is available but should be independently validated in the target deployment environment.

## Application structure

```text
MediBridge/
├── accounts/          # Custom user, patient/doctor profiles, registration, JWT APIs
├── organizations/     # Diagnostic centers and center memberships
├── patients/          # Relationships, consultations, clinical observations
├── diagnostics/       # Services, requests, attachments, reports, AI analyses
├── prescriptions/     # Prescriptions, medication items, prescription PDFs
├── config/            # Django settings, URL configuration, renderers
├── docs/              # Architecture, setup, API, security documentation
├── docs/swagger/      # Static OpenAPI document and Swagger UI
├── samples/           # Demonstration sample assets; review redistribution rights
├── manage.py
├── requirements.txt
└── .env.example
```

For the domain model, authorization boundaries, and lifecycle diagrams, see [Architecture](docs/ARCHITECTURE.md).

## Run locally

### 1. Create a virtual environment

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

If `.env` already exists, do not overwrite it. Set a unique, high-entropy `SECRET_KEY`; keep `.env` out of source control. The sample configuration is intended for local development only.

### 4. Apply migrations and create an administrator

```bash
python manage.py migrate
python manage.py createsuperuser
```

Create demo doctor profiles, diagnostic centers, and center memberships through the authorized local setup process or Django admin. Center staff require an active membership for the relevant center. Doctors need an approved profile for doctor-specific operations.

### 5. Start the server

```bash
python manage.py runserver
```

| Resource | Local URL |
|---|---|
| Health check | `http://127.0.0.1:8000/api/health/` |
| Interactive Swagger UI | `http://127.0.0.1:8000/api/docs/` |
| ReDoc | `http://127.0.0.1:8000/api/redoc/` |
| OpenAPI schema | `http://127.0.0.1:8000/api/schema/` |
| Django admin | `http://127.0.0.1:8000/admin/` |

See [Setup and Reproducibility](docs/SETUP.md) for environment configuration, AI runtime notes, and verification commands. See [API Guide](docs/API_GUIDE.md) for endpoint groups and workflows.

## End-to-end workflows

### Patient–doctor and clinical-record workflow

1. A patient creates a relationship request for an approved doctor.
2. The requested doctor accepts the relationship.
3. The connected doctor creates and signs a consultation.
4. The doctor records clinical observations; the patient can also add supported patient-reported observations to their own record.
5. Either the patient or the connected doctor can revoke the relationship, subject to the endpoint's authorization rules.

### Diagnostic investigation and report workflow

1. A patient or eligible clinician creates a diagnostic request for a service.
2. Authorized center staff accept and start the request.
3. Center staff upload an eligible attachment to the in-progress request.
4. For a supported chest X-ray service, authorized staff can run AI inference.
5. An authorized reviewer reviews the AI analysis. The report preparer and report verifier must be different users.
6. Center staff submit the diagnostic report, optionally linking an accepted AI analysis.
7. An authorized verifier verifies the report; an authorized user releases it.
8. The request is marked completed. The patient can retrieve the released report and download its PDF. An authorized doctor can retrieve reports allowed by the ordering-doctor or active-relationship access rules.

### Prescription workflow

1. An approved doctor with an active patient relationship creates a draft prescription.
2. The doctor adds one or more structured medication items and instructions.
3. The issuing doctor issues the prescription.
4. The patient can retrieve their issued prescription and download its PDF. Other patients cannot access it.

## AI scope, interpretation, and limitations

The current AI integration uses TorchXRayVision DenseNet121 with `densenet121-res224-all` weights for the supported chest X-ray workflow. The integration records the selected model, source attachment, request, submitter, analysis status, pathology scores, score semantics, and human-review information.

AI scores are model outputs, **not calibrated probabilities, confirmed findings, or diagnoses**. The application requires an accepted human review before an analysis snapshot is included in a diagnostic report. Clinician-authored findings and impression remain separate from the AI-assistance data.

The model is not intended for diabetic-foot-ulcer photographs, PDFs, or unrelated imaging modalities. This integration is an engineering demonstration and has not been clinically validated or approved as a regulated diagnostic device.

## Security and data handling

Implemented controls include role-aware permissions, patient ownership checks, doctor–patient relationship checks, diagnostic-center membership checks, report release restrictions, independent report verification, validated file uploads, private diagnostic attachment storage, and authorization before file/PDF downloads.

Automated tests cover registration rules, AI inference validation, diagnostic authorization, patient–doctor relationship operations, consultation workflows, observation access, and selected cross-patient/cross-center restrictions. The latest reported local run passed **27 automated tests**. This is meaningful regression coverage, not a substitute for a formal security audit or penetration test.

Before any hosted deployment:

- Use synthetic or appropriately licensed demonstration data only.
- Never commit `.env`, database files, private attachments, access tokens, or credentials.
- Keep diagnostic files in private storage; do not expose private uploads through public media URLs.
- Set `DEBUG=False`, a unique secret key, and a strict `ALLOWED_HOSTS` configuration.
- Configure HTTPS, secure cookies/headers, database and storage protection, backups, monitoring, alerting, and operational procedures.
- Complete privacy, legal, regulatory, and clinical reviews appropriate to the deployment jurisdiction and intended use.

## Verification status

Latest reported local verification:

| Check | Result |
|---|---|
| `python manage.py test -v 2` | **27 tests passed** |
| Django system check during test run | No issues reported |
| `python manage.py spectacular --file schema.yml --validate` | **0 errors; 24 warnings across 10 unique warning categories** |
| AI-assisted report workflow | Manually completed; released report contained 18 AI scores with review status `ACCEPTED` |
| Diagnostic report PDF download | Manually verified successfully |
| Prescription PDF download | Manually verified successfully after correcting the action's PDF renderer configuration |

The remaining OpenAPI warnings concern serializer method return-type hints and UUID-like path-parameter type inference. They do not prevent schema generation, but should be resolved in a future documentation-quality pass. See [Security and Verification](docs/SECURITY_AND_VERIFICATION.md) for test coverage and boundaries.

## Current boundaries and future scope

MediBridge is a backend demonstration; it does not include a patient or doctor frontend, dashboard, or automatic report-notification service. Doctors retrieve authorized reports through the report list, detail, and PDF download API operations.

A `PatientConsent` model exists, but the current API schema does not expose a separate consent-management endpoint. The relationship workflow should therefore not be represented as a complete granular consent-management system.

The backend has not been deployed as a public API service. GitHub Pages hosts the project landing page and a static Swagger reference only. Production deployment, comprehensive audit logging, rate limiting/abuse controls, backup/restore exercises, formal security testing, clinical validation, and regulatory review remain outside the demonstrated scope.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Setup and Reproducibility](docs/SETUP.md)
- [API Guide](docs/API_GUIDE.md)
- [Security and Verification](docs/SECURITY_AND_VERIFICATION.md)
- [OpenAPI / Swagger reference](https://jim8489.github.io/MediBridge/swagger/)

---

**MediBridge — structured healthcare coordination, controlled diagnostic workflows, and human-reviewed AI assistance.**
