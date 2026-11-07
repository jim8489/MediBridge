# MediBridge — Setup and Reproducibility

This guide describes how to install and run the MediBridge backend locally, configure its environment, initialize the database, and verify the main application components.

## 1. Prerequisites

The development environment used for the project was Python 3.11.3 on macOS Apple Silicon. The project uses Django 5.2, Django REST Framework, Simple JWT, drf-spectacular, PyTorch, TorchVision, TorchXRayVision, and ReportLab.

SQLite is the default local database. The settings also support a PostgreSQL connection URL through `dj-database-url` and `psycopg`. Local verification reported in this repository's development history used SQLite; a hosted PostgreSQL deployment should be validated independently.

## 2. Create a virtual environment

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Confirm that the expected interpreter is active:

```bash
python --version
which python
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

The repository's requirements file includes the application dependencies, including ReportLab for report and prescription PDFs. Install from that file rather than manually installing individual packages unless you are resolving a platform-specific dependency issue.

The AI stack is version-sensitive. The current requirements pin the PyTorch, TorchVision, and TorchXRayVision packages used by the project. Preserve the known project versions when reproducing the demonstrated inference path; validate any version change with a fresh model-load and inference test.

## 4. Configure environment variables

Create a local `.env` file from the template:

```bash
cp .env.example .env
```

If `.env` already exists, do not overwrite it. Review and set the values appropriate for your local environment.

The template uses the following configuration concepts:

```env
SECRET_KEY=replace-this-with-a-long-random-secret-key
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
TIME_ZONE=Asia/Dhaka
DATABASE_URL=sqlite:///db.sqlite3
```

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django signing and cryptographic secret. Use a unique, high-entropy value. |
| `DEBUG` | Enables/disables Django debug mode. `True` is for local development only. |
| `ALLOWED_HOSTS` | Comma-separated host allowlist. |
| `TIME_ZONE` | Application timezone; the local project configuration uses `Asia/Dhaka`. |
| `DATABASE_URL` | Database URL parsed by `dj-database-url`. |

Do not use the example secret key in a hosted environment. Production configuration requires `DEBUG=False`, a strict host allowlist, HTTPS, secure cookie/header settings, protected secrets, and review of Django's deployment checks.

## 5. Initialize the database

### SQLite (default local setup)

The local template uses:

```env
DATABASE_URL=sqlite:///db.sqlite3
```

Apply the existing migrations:

```bash
python manage.py migrate
```

### PostgreSQL (configurable alternative)

The settings parse PostgreSQL URLs using `dj-database-url` and the psycopg driver. Example format:

```env
DATABASE_URL=postgresql://medibridge_user:replace_me@127.0.0.1:5432/medibridge_db
```

Create the database and database role separately, configure the URL in `.env`, and then apply migrations:

```bash
python manage.py migrate
```

Database TLS, credentials, network restrictions, backups, and provider-specific hardening must be configured for the target environment. Merely supplying a PostgreSQL URL does not make a deployment production-ready.

## 6. Create an administrator and prepare demo roles

Create a Django administrator:

```bash
python manage.py createsuperuser
```

Use the Django admin or the project's authorized local provisioning process to create:

- Approved doctor profiles.
- Diagnostic-center records.
- Diagnostic-center staff users and active center memberships.
- Demo patient accounts.

A diagnostic staff user must have an active membership in the center associated with the request/service. Doctor operations that require a clinical relationship depend on an approved doctor profile and an active patient–doctor relationship.

Use synthetic demo identities and data. Do not place actual patient information, production credentials, JWTs, or private uploaded files in the repository or demonstration material.

## 7. Start the development server

```bash
python manage.py runserver
```

Local endpoints:

| Resource | URL |
|---|---|
| Interactive Swagger UI | `http://127.0.0.1:8000/api/docs/` |
| ReDoc | `http://127.0.0.1:8000/api/redoc/` |
| OpenAPI schema | `http://127.0.0.1:8000/api/schema/` |
| Health check | `http://127.0.0.1:8000/api/health/` |
| Django admin | `http://127.0.0.1:8000/admin/` |

The public GitHub Pages Swagger site is a static, read-only reference. It is not connected to a hosted backend. Use the local Swagger UI to execute requests against the development server.

## 8. AI runtime setup

The current inference integration uses TorchXRayVision DenseNet121 with `densenet121-res224-all` weights. The model registry and inference module process eligible chest X-ray attachments associated with the supported diagnostic service.

Verify that the AI packages import correctly:

```bash
python -c "import torch, torchvision, torchxrayvision; print('torch', torch.__version__); print('torchvision', torchvision.__version__); print('torchxrayvision', torchxrayvision.__version__)"
```

Model weights may be downloaded or cached during first initialization, depending on the environment. Ensure the runtime can access the required weights before executing an API analysis request.

The analysis endpoint is restricted to the supported chest X-ray workflow and eligible clinical image attachments (JPEG/PNG). The model is not intended for diabetic-foot-ulcer photographs, PDFs, or other imaging modalities.

The model returns pathology scores with score semantics. These values are model outputs, not calibrated probabilities or diagnoses. An authorized human reviewer must accept the analysis before it can be incorporated into a diagnostic report.

## 9. Sample assets and data handling

The repository contains demonstration sample assets under `samples/`. Before redistributing any sample publicly or using it in an external demonstration, confirm its source and applicable license/redistribution rights. Use synthetic or appropriately licensed data only; do not commit identifiable patient images or medical records.

Private diagnostic uploads are intended to remain in private storage. Do not serve them through public media URLs or include the storage directory in Git commits.

## 10. Run verification checks

Run the project's automated tests and schema validation:

```bash
python manage.py check
python -m compileall accounts patients diagnostics prescriptions organizations config
python manage.py test -v 2
python manage.py spectacular --file schema.yml --validate
```

The latest reported local run produced these results:

| Check | Result |
|---|---|
| Django system check | No issues reported during the test run. |
| Automated Django tests | **27 tests passed.** |
| OpenAPI generation | **0 errors; 24 warnings across 10 unique categories.** |

The remaining schema warnings include unresolved return-type hints for the current-user patient/doctor profile serializer methods and UUID-like path-parameter type inference in several viewsets. Schema generation succeeds, but these warnings should be addressed in a future API-documentation cleanup.

After regenerating the root schema, update the static Swagger document:

```bash
cp schema.yml docs/swagger/openapi.yml
```

Review the generated diff before committing it. The generated OpenAPI schema is the reference for exact request fields, route actions, and response content types.

## 11. Git hygiene

The repository's ignore rules are intended to exclude local secrets, local databases, virtual environments, cache files, and private uploaded media. Before committing, review the staged files:

```bash
git status --short
git diff --cached --stat
git diff --cached
```

Do not commit:

- `.env` or any other secret-bearing configuration file.
- Local SQLite databases or production database dumps.
- `private_media/` or private diagnostic attachments.
- JWT access/refresh tokens, passwords, or API keys.
- Identifiable patient information.
- Sample files whose redistribution rights have not been established.

## 12. Troubleshooting

### A Python dependency cannot be imported

Confirm that the virtual environment is active and install the pinned project dependencies:

```bash
which python
python -m pip install -r requirements.txt
```

### The AI model cannot initialize

Check the installed PyTorch/TorchVision/TorchXRayVision versions, model-weight availability, and application logs. Confirm the request is for the supported chest X-ray service and that the uploaded attachment is an eligible image.

### Database connection fails

Check `DATABASE_URL`, database availability, database name, user privileges, and network access. For SQLite, verify that the project directory is writable.

### Swagger shows an unexpected request or response schema

Regenerate and validate the schema:

```bash
python manage.py spectacular --file schema.yml --validate
cp schema.yml docs/swagger/openapi.yml
```

Then refresh local Swagger. For a public GitHub Pages update, commit and push the refreshed `docs/swagger/openapi.yml` file.

## 13. Production-readiness boundary

This guide supports local development and reproducibility; it is not a production deployment runbook. A production rollout requires environment-specific server configuration, secret management, HTTPS, secure database and private-file storage, backup/restore testing, monitoring and alerting, rate limiting/abuse controls, audit logging, security assessment, privacy/legal review, and appropriate clinical evaluation. None of those should be assumed complete solely because the local API and automated tests pass.
