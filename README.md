# MediBridge

**Healthcare Coordination and AI-Assisted Diagnostics — Backend**

MediBridge is a Django REST Framework backend for coordinating clinical and diagnostic workflows between patients, doctors, and diagnostic centers. It combines role-aware access to patient records, consultations, diagnostic investigations, prescriptions, secure document handling, and human-reviewed AI-assisted chest X-ray analysis.

> **Project status:** Internship demonstration backend. The implementation excerpts and local verification output shared during development show a working Django API, report and prescription PDF generation, a TorchXRayVision inference integration, and six passing automated tests at the latest reported test run. Full security regression testing and production hardening remain outstanding.

## Contents

- [Capabilities](#capabilities)
- [Roles](#roles)
- [Technology](#technology)
- [Application structure](#application-structure)
- [Quick start](#quick-start)
- [API documentation](#api-documentation)
- [Core workflows](#core-workflows)
- [AI scope and limitations](#ai-scope-and-limitations)
- [Security and data handling](#security-and-data-handling)
- [Validation commands](#validation-commands)
- [Documentation](#documentation)

## Capabilities

- Custom email-based user model with UUID identifiers.
- JWT authentication and role-based API access.
- Patient and doctor profiles.
- Doctor–patient relationships and consent/relationship actions.
- Diagnostic centers and staff memberships.
- Consultations and clinical observations.
- Diagnostic service catalogue and diagnostic requests.
- Private diagnostic attachments with file validation and authorized downloads.
- Diagnostic report preparation, independent verification, release, and PDF download.
- Prescription creation, structured medication items, issue workflow, and PDF download.
- AI model registration and traceable analysis records.
- TorchXRayVision DenseNet121 integration for supported chest X-ray services.
- Human review of AI analyses before attaching an AI result snapshot to a diagnostic report.
- OpenAPI schema, Swagger UI, and ReDoc.

## Roles

| Role | Intended responsibilities |
|---|---|
| Patient | Access their own clinical information, create or follow permitted diagnostic requests, and view released reports and issued prescriptions. |
| Doctor | Work with patients through authorized relationships, manage consultations and observations, and create/issue prescriptions subject to verification and relationship rules. |
| Diagnostic staff | Work on requests assigned to their diagnostic center, upload permitted attachments, run supported AI analysis, and prepare reports. |
| Report verifier | Independently verify and release reports when the user's center membership grants verifier authority. |
| Administrator | Perform authorized administrative and account-management tasks. |

The exact access available to a particular user depends on both the role and the relevant resource relationship or center membership. A role label alone is not a substitute for object-level authorization.

## Technology

| Area | Technology/configuration |
|---|---|
| Language | Python 3.11 (3.11.3 used in local development) |
| Web framework | Django 5.2 |
| API | Django REST Framework |
| Authentication | djangorestframework-simplejwt |
| API schema | drf-spectacular / OpenAPI |
| Development database | SQLite |
| Alternative database configuration | PostgreSQL URL via dj-database-url and psycopg |
| AI runtime | PyTorch, TorchVision, TorchXRayVision |
| AI model | DenseNet121, `densenet121-res224-all` weights |
| PDF generation | ReportLab (local environment version reported: 5.1.0) |
| Configuration | python-dotenv and environment variables |

## Application structure

```text
MediBridge/
├── accounts/          # Custom user, profiles, registration, JWT/current-user APIs
├── organizations/     # Diagnostic centers and center memberships
├── patients/          # Doctor–patient relationships, consultations, observations
├── diagnostics/       # Services, requests, attachments, reports, AI analyses
├── prescriptions/     # Prescriptions, medication items, prescription PDFs
├── config/            # Django settings, root URLs, ASGI/WSGI
├── docs/              # Project documentation
├── samples/           # Demonstration sample(s), subject to redistribution checks
├── manage.py
├── requirements.txt
└── .env.example
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the conceptual model relationships and workflows.

## Quick start

### 1. Create and activate a virtual environment

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

**Dependency note:** the `requirements.txt` shown during project review did not yet list ReportLab, although the local environment reported `reportlab==5.1.0` and both PDF features were working. Add this line to `requirements.txt` before relying on a fresh installation:

```text
reportlab==5.1.0
```

### 3. Configure environment

```bash
cp .env.example .env
```

If `.env` already exists, do not overwrite it. Set a unique `SECRET_KEY` and keep `.env` out of version control. The supplied template is for local development, not production.

### 4. Apply migrations and create an administrator

```bash
python manage.py migrate
python manage.py createsuperuser
```

The project contains migrations. For a normal clone/setup, applying them with `migrate` is sufficient; do not create new migrations unless models have intentionally changed.

### 5. Run the API

```bash
python manage.py runserver
```

Useful local URLs:

| Resource | URL |
|---|---|
| Health check | `http://127.0.0.1:8000/api/health/` |
| Swagger UI | `http://127.0.0.1:8000/api/docs/` |
| ReDoc | `http://127.0.0.1:8000/api/redoc/` |
| OpenAPI schema | `http://127.0.0.1:8000/api/schema/` |
| Django admin | `http://127.0.0.1:8000/admin/` |

For detailed setup and AI environment notes, see [docs/SETUP.md](docs/SETUP.md). For endpoint groups and workflow examples, see [docs/API_GUIDE.md](docs/API_GUIDE.md).

## API documentation

The generated OpenAPI schema is the source of truth for exact request fields, response schemas, action routes, and accepted parameters. Some router actions and nested routes should be checked in Swagger rather than inferred from this summary.

All API paths are rooted under `/api/`. Most endpoints require JWT authentication. Obtain a token at `POST /api/auth/token/` and authorize Swagger using the access token.

## Core workflows

### Diagnostic investigation

1. A patient or authorized doctor creates a diagnostic request.
2. Eligible center staff act on the request through the diagnostic workflow.
3. Center staff upload a clinical image or document while the investigation is in the permitted state.
4. For supported chest X-ray services, staff can request AI analysis.
5. An authorized reviewer reviews the AI output.
6. Center staff submit a diagnostic report, optionally referencing an accepted AI analysis.
7. A different authorized verifier verifies and releases the report.
8. The patient can access the released report and download its PDF.

### Prescription

1. An approved doctor with an active patient relationship creates a draft prescription.
2. The prescription contains one or more structured medication items and general instructions.
3. The issuing doctor issues the prescription.
4. The patient can access their issued prescription and download its PDF.

## AI scope and limitations

The integrated model is TorchXRayVision DenseNet121 with `densenet121-res224-all` weights. The current API checks that the requested diagnostic service is a chest X-ray service before running this model.

The model produces pathology scores with associated score semantics. Those scores are not calibrated probabilities and are not, by themselves, diagnoses. The system records the model, source attachment, analysis status, scores, review status, reviewer, notes, and timestamps. The intended report workflow keeps AI decision-support output separate from clinician-entered findings and impression, and requires an accepted/reviewed analysis before including it.

Do not use this chest X-ray model for DFU photographs, PDFs, or other imaging modalities. The integration is an engineering demonstration and has not been established as a clinically validated or regulated diagnostic device.

## Security and data handling

Implemented safeguards visible in the shared source include role checks, patient ownership checks, doctor–patient relationship checks, active diagnostic-center membership checks, report release restrictions, independent report verification, file validation, and private attachment streaming after authorization.

Before sharing or deploying the project:

- Use synthetic or appropriately licensed demonstration data only.
- Never commit `.env`, database files, private medical attachments, or credentials.
- Keep diagnostic attachments in private storage; do not expose them using public media URLs.
- Use a unique secret key and disable debug mode in a deployment.
- Configure TLS, secure cookies/headers, database access restrictions, backups, monitoring, and operational controls for any hosted environment.
- Complete the planned automated security regression tests. The current test count is not a substitute for a security audit or penetration test.

## Validation commands

```bash
python manage.py check
python -m compileall diagnostics prescriptions
python manage.py spectacular --file schema.yml --validate
python manage.py test
```

The latest local verification shared on 6 November 2026 reported:

- Django system check: no issues.
- Python compile check for `diagnostics` and `prescriptions`: completed.
- OpenAPI generation: zero errors, with 24 warnings (10 unique categories) remaining.
- Django test suite: six tests passed.

These results describe that reported local run only. The planned full role-based security regression suite and fresh end-to-end AI-assisted report test were still outstanding at that point.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Setup and reproducibility](docs/SETUP.md)
- [API guide](docs/API_GUIDE.md)
- [Security and verification status](docs/SECURITY_AND_VERIFICATION.md)

## Project status and intended use

MediBridge is an internship demonstration backend, not a production-certified clinical system. It requires further automated authorization testing, deployment hardening, operational safeguards, privacy/regulatory review, and clinical evaluation before any real-world clinical use.
