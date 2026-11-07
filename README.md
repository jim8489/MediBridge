# MediBridge — Phase 02 Backend Starter

MediBridge is a healthcare coordination backend connecting patients, doctors, and diagnostic centers.

This starter contains **Milestone 1**:
- Django project foundation
- Custom email-based User model with UUID identifiers
- Patient and doctor profiles
- Diagnostic center and center memberships
- Doctor–patient relationship and patient consent records
- Patient-only public registration
- JWT login with role/email claims
- Current-user endpoint
- Swagger / OpenAPI documentation
- Basic API tests

The clinical workflow (consultations, observations, diagnostic requests/reports, prescriptions, AI analysis) is the next milestone. Do not add those models before this foundation migrates successfully.

## Requirements

- Python 3.10+
- macOS, Linux, or Windows
- Git

Django 5.2 is used as the LTS line. Django's official compatibility table lists Python 3.10–3.14 for Django 5.2. See https://docs.djangoproject.com/en/5.2/faq/install/.

## 1. Create and activate a virtual environment

```bash
cd MediBridge
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 2. Configure environment

```bash
cp .env.example .env
```

The default `.env.example` uses SQLite so you can start immediately. The project also supports PostgreSQL through `DATABASE_URL`; see the PostgreSQL section below.

## 3. Create database tables

```bash
python manage.py makemigrations accounts organizations patients
python manage.py migrate
```

## 4. Create the admin account

```bash
python manage.py createsuperuser
```

The superuser receives the `ADMIN` role automatically.

## 5. Run the API

```bash
python manage.py runserver
```

Open:
- Swagger UI: http://127.0.0.1:8000/api/docs/
- OpenAPI schema: http://127.0.0.1:8000/api/schema/
- Django admin: http://127.0.0.1:8000/admin/
- Health check: http://127.0.0.1:8000/api/health/

## API endpoints in this milestone

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| POST | `/api/auth/register/` | Register a patient account | Public; patient role only |
| POST | `/api/auth/token/` | Obtain JWT access and refresh tokens | Public |
| POST | `/api/auth/token/refresh/` | Refresh access token | Public with refresh token |
| GET | `/api/auth/me/` | Get current user and profile | Authenticated |
| GET | `/api/health/` | API health check | Public |

### Example patient registration

```json
{
  "email": "patient@example.com",
  "first_name": "Rahim",
  "last_name": "Ahmed",
  "phone": "+8801XXXXXXXXX",
  "password": "ChangeThisStrongPassword123!",
  "password_confirm": "ChangeThisStrongPassword123!"
}
```

Registration always creates a `PATIENT` user and a linked `PatientProfile`. The public endpoint intentionally does **not** accept a role field. Doctor and diagnostic staff accounts should be created by an administrator and linked to verified profiles/organizations.

### Example login

```json
{
  "email": "patient@example.com",
  "password": "ChangeThisStrongPassword123!"
}
```

Use the returned access token in Swagger's **Authorize** dialog as a Bearer token. Paste the token only, without adding `Bearer ` if Swagger's security scheme handles it automatically.

## Create a doctor account for development

Create a user via Django admin or Django shell, then create the doctor's profile. Example shell commands:

```bash
python manage.py shell
```

```python
from accounts.models import User, DoctorProfile

user = User.objects.create_user(
    email="doctor@example.com",
    password="ChangeThisStrongPassword123!",
    first_name="Ahmed",
    last_name="Khan",
    role=User.Role.DOCTOR,
)
DoctorProfile.objects.create(
    user=user,
    license_number="DEMO-BMDC-0001",
    specialization="General Medicine",
    qualification="MBBS (demo data)",
    verification_status=DoctorProfile.VerificationStatus.APPROVED,
)
```

For a real product, professional credentials require an actual verification process. The sample data above is for local testing only.

## Create a diagnostic center and staff member

```python
from accounts.models import User
from organizations.models import DiagnosticCenter, CenterMembership

center = DiagnosticCenter.objects.create(
    name="MediBridge Demo Diagnostics",
    registration_number="DEMO-CENTER-0001",
    email="center@example.com",
    phone="+8801XXXXXXXXX",
    address="Rangpur, Bangladesh",
    verification_status=DiagnosticCenter.VerificationStatus.APPROVED,
)

staff = User.objects.create_user(
    email="staff@example.com",
    password="ChangeThisStrongPassword123!",
    first_name="Lab",
    last_name="Staff",
    role=User.Role.DIAGNOSTIC_STAFF,
)
CenterMembership.objects.create(
    center=center,
    user=staff,
    staff_role=CenterMembership.StaffRole.CENTER_ADMIN,
    status=CenterMembership.Status.ACTIVE,
)
```

## PostgreSQL configuration

The project uses SQLite by default for the fastest first run. For PostgreSQL, create a database and change `.env`:

```env
DATABASE_URL=postgresql://medibridge_user:your_password@127.0.0.1:5432/medibridge_db
```

Then run migrations again against that database:

```bash
python manage.py migrate
```

Install and start PostgreSQL locally with your preferred method (for example, Homebrew or Postgres.app). Do not commit `.env` or database credentials.

## Run tests

```bash
python manage.py test accounts patients organizations
```

## Git setup

```bash
git init
git add .
git commit -m "Initialize MediBridge backend foundation"
```

## Important security notes

- This is a development starter, not a production-ready clinical system.
- Use synthetic data only for the internship demo. Never upload real patient records.
- Do not expose medical files through public media URLs.
- All clinical endpoints added in later milestones must enforce object-level authorization, not only role checks.
- The API does not yet implement patient/doctor workflow endpoints; those are the next coding milestone.
