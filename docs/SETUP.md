# MediBridge — Setup and Reproducibility

## 1. Prerequisites

The development environment used for this project was Python 3.11.3 on macOS Apple Silicon. The project uses Django 5.2, Django REST Framework, Simple JWT, drf-spectacular, PyTorch, TorchVision, TorchXRayVision, and ReportLab.

SQLite is the default local database. The settings also parse a PostgreSQL connection URL through `dj-database-url` and `psycopg`.

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

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

The `requirements.txt` content shared during review included Django, DRF, Simple JWT, drf-spectacular, dj-database-url, psycopg, python-dotenv, PyTorch, TorchVision, and TorchXRayVision.

**Important reproducibility correction:** ReportLab was installed in the development environment at version `5.1.0`, and report/prescription PDFs were working, but the `requirements.txt` content shared for review did not include it. Add the following exact line to `requirements.txt`:

```text
reportlab==5.1.0
```

Then verify with:

```bash
python -c "import reportlab; print(reportlab.Version)"
```

The Torch/TorchVision versions in the existing requirements file were reported as `torch==2.15.0` and `torchvision==0.29.2`. Preserve the project's known-working environment while documenting any future compatibility changes with a fresh inference test.

## 4. Configure environment variables

Create `.env` from the template if it does not already exist:

```bash
cp .env.example .env
```

Do not overwrite an existing local `.env` file. The template shared during review was:

```env
SECRET_KEY=replace-this-with-a-long-random-secret-key
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
TIME_ZONE=Asia/Dhaka
DATABASE_URL=sqlite:///db.sqlite3
```

Settings load `.env` from the project root using `python-dotenv`.

| Variable | Use |
|---|---|
| `SECRET_KEY` | Django signing and cryptographic secret. |
| `DEBUG` | Django debug flag. |
| `ALLOWED_HOSTS` | Comma-separated host allowlist. |
| `TIME_ZONE` | Application timezone; local project configuration uses `Asia/Dhaka`. |
| `DATABASE_URL` | Database URL parsed by `dj-database-url`. |

The `SECRET_KEY` fallback in the shared settings is an unsafe development placeholder. Set a unique secret key in every real deployment. The example `DEBUG=True` is only for local development. Production deployment requires `DEBUG=False`, correctly configured hosts, HTTPS, secure cookie/header settings, and review of all Django deployment checks.

## 5. Database setup

### SQLite

The default template uses:

```env
DATABASE_URL=sqlite:///db.sqlite3
```

Run migrations:

```bash
python manage.py migrate
```

### PostgreSQL

The settings use `dj-database-url` and the psycopg driver. An example URL is:

```env
DATABASE_URL=postgresql://medibridge_user:replace_me@127.0.0.1:5432/medibridge_db
```

Create the database and role first, set the URL in `.env`, then run:

```bash
python manage.py migrate
```

The shared settings parse the URL with `conn_max_age=600` and `ssl_require=False`. A hosted PostgreSQL deployment must be configured according to its provider's TLS/security requirements; the shared settings alone do not establish production database security.

## 6. Create an administrator

```bash
python manage.py createsuperuser
```

Use the Django admin and approved local setup procedures to create development doctor profiles, diagnostic centers, and center memberships. A diagnostic staff user needs an active membership for the correct center to operate on that center's requests. An approved doctor profile and active patient relationship are required for prescription creation.

Use clearly synthetic credentials and test data. Never put actual patient information or production credentials in the repository.

## 7. Start the development server

```bash
python manage.py runserver
```

Open:

- Swagger: `http://127.0.0.1:8000/api/docs/`
- ReDoc: `http://127.0.0.1:8000/api/redoc/`
- Schema: `http://127.0.0.1:8000/api/schema/`
- Health: `http://127.0.0.1:8000/api/health/`
- Admin: `http://127.0.0.1:8000/admin/`

## 8. AI runtime setup

The current analysis path uses TorchXRayVision DenseNet121 with `densenet121-res224-all` weights. The model registry loads/registers the model and the inference module processes eligible chest X-ray attachments.

Verify package imports:

```bash
python -c "import torch, torchvision, torchxrayvision; print('torch', torch.__version__); print('torchvision', torchvision.__version__); print('torchxrayvision', torchxrayvision.__version__)"
```

The model weights may be downloaded/cached at first initialization, depending on the environment. Confirm that the runtime can access the model weights before attempting the API workflow.

The endpoint checks for a chest X-ray service. Use a supported chest X-ray JPEG/PNG attachment. The model is not intended for DFU images, PDFs, or other imaging modalities.

AI scores are model outputs with associated score semantics. They are not calibrated probabilities or confirmed diagnoses. The report workflow requires human review before adding AI information to a report.

## 9. Sample data

The project structure shared during review included `samples/sample_chest_xray.jpg`. Confirm its source and redistribution rights before publishing it in a public repository. Use synthetic or appropriately licensed data only. Do not include identifiable patient data.

## 10. Run checks and tests

```bash
python manage.py check
python -m compileall diagnostics prescriptions
python manage.py spectacular --file schema.yml --validate
python manage.py test
```

The latest test output shared during the documentation review reported six tests passing. OpenAPI generation reported zero errors but 24 warnings (10 unique categories), including unresolved serializer method return types and path-parameter types. These warnings should be reviewed; zero schema errors does not mean there are no documentation issues.

## 11. Git hygiene

Before publishing, verify that `.gitignore` excludes at least:

```gitignore
.venv/
venv/
__pycache__/
*.py[cod]
*.sqlite3
.env
.DS_Store
.pytest_cache/
.coverage
htmlcov/
media/
private_media/
staticfiles/
```

The `.gitignore` content shared for review already excluded `.env`, SQLite files, virtual environments, cache files, `media/`, and `staticfiles/`, but did not include `private_media/`. Add `private_media/` before the first commit so private diagnostic files cannot be accidentally staged.

Also inspect the staged changes before committing:

```bash
git status --short
git diff --cached --stat
git diff --cached
```

Do not commit `.env`, `db.sqlite3`, real patient records, private uploads, or unlicensed samples.

## 12. Troubleshooting

### A dependency cannot be imported

Confirm the virtual environment is active, then install requirements again:

```bash
which python
python -m pip install -r requirements.txt
```

### The AI model cannot initialize

Check PyTorch/TorchVision/TorchXRayVision versions, model-weight availability, and the application logs. Confirm the service is a supported chest X-ray service and the attachment is an eligible image.

### Database connection fails

Check the `DATABASE_URL`, database service state, database name, user privileges, and network access. For SQLite, check project-directory write permissions.

### Swagger shows an unexpected request schema

Regenerate the schema and inspect the affected operation:

```bash
python manage.py spectacular --file schema.yml --validate
```

The generated OpenAPI document and live Swagger UI should agree. Hard refresh the browser after schema changes.

## 13. Production readiness note

This guide supports local reproducibility. It is not a production deployment guide. A production rollout requires a secure secret-management approach, HTTPS, production server configuration, secure database and private file storage, backups and restore tests, monitoring, rate limiting, security review, privacy/legal review, and appropriate clinical validation.
