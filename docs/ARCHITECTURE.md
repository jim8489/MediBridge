# MediBridge — Architecture

## 1. Architectural overview

MediBridge is a modular Django REST Framework backend. The application separates identity and authentication, organizational membership, clinical relationships, diagnostic operations, AI analysis, and prescription management into Django apps.

```text
 Patient / Doctor / Diagnostic Center Staff
                    |
                    v
             Django REST API
                    |
                    v
          JWT Authentication
                    |
                    v
        Role + Resource Authorization
                    |
       +------------+-------------+
       |            |             |
       v            v             v
    accounts   organizations   patients
       |            |             |
       |            |             +-- Doctor–patient relationships
       |            |             +-- Consultations
       |            |             +-- Observations
       |            |
       |            +-- Diagnostic centers
       |            +-- Center memberships
       |
       +-- User / patient / doctor profiles
                    |
          +---------+---------+
          |                   |
          v                   v
      diagnostics         prescriptions
          |                   |
          +-- Services        +-- Prescription
          +-- Requests        +-- Prescription items
          +-- Attachments     +-- Prescription PDF
          +-- Reports
          +-- AI model registry
          +-- AI analyses
          +-- Diagnostic report PDF
```

This diagram is conceptual. Django model definitions, serializers, viewsets, URL configuration, and generated OpenAPI schema are the authoritative implementation.

## 2. Application responsibilities

### `accounts`

Owns the custom user model and identity-related APIs. The user model uses UUID identifiers and email-based authentication. The app also contains patient/doctor profile concepts, patient registration, JWT token endpoints, and the current-user endpoint.

### `organizations`

Owns diagnostic-center organizations and staff memberships. Center memberships associate a diagnostic staff user with a center and a staff role/status. Center approval and active membership are relevant to center-specific access.

### `patients`

Owns doctor–patient relationships, consultations, and observations. The active relationship is used by prescription creation and doctor access rules. Consultation validation also checks that the consultation belongs to the selected patient and doctor and is signed where required.

### `diagnostics`

Owns diagnostic services, requests, attachments, reports, AI model registration, and AI analyses. It implements the investigation workflow, private attachment upload/download, AI analysis/review actions, report submission, verification/release, and diagnostic report PDF generation.

### `prescriptions`

Owns prescriptions and medication items. A prescription is related to a patient and doctor, may be linked to a consultation, and includes structured medication instructions. The app provides issue and PDF-download actions.

## 3. Domain relationships

The following is a simplified relationship map; it is not a substitute for the model files:

```text
User
 |-- PatientProfile
 |      |-- DoctorPatientRelationship -- DoctorProfile -- User
 |      |-- Consultation
 |      |      `-- Observation
 |      |-- DiagnosticRequest
 |      |      |-- DiagnosticAttachment
 |      |      |      `-- AIAnalysis -- AIModel
 |      |      `-- DiagnosticReport (one-to-one)
 |      `-- Prescription
 |             `-- PrescriptionItem
 |
 |-- DoctorProfile
 `-- CenterMembership -- DiagnosticCenter
                              `-- DiagnosticService
                                      `-- DiagnosticRequest
```

Important model-level details confirmed in the shared source:

- `DiagnosticReport.request` is a one-to-one relation to a diagnostic request, with `PROTECT` deletion behavior.
- `DiagnosticAttachment.request` is a foreign key with `PROTECT` deletion behavior and a related name of `attachments`.
- `AIAnalysis` refers to a diagnostic request, source attachment, registered AI model, submitting user, and optional reviewer.
- `Prescription` refers to a patient, doctor, and optional consultation.
- `PrescriptionItem` belongs to a prescription and stores medicine and administration fields.

## 4. Roles and access control

Authorization is based on the authenticated user role plus the relevant resource relationship or organization membership.

### Patient

The shared view code restricts a patient report queryset to reports for that patient's profile with `RELEASED` status. Prescription queryset logic restricts patients to their own prescriptions with `ISSUED` status. Diagnostic attachment download additionally checks patient ownership and that the associated report has been released.

### Doctor

Doctor report access is based on the ordering doctor or an active doctor–patient relationship. Prescription creation requires an approved doctor profile and an active relationship with the selected patient. If a consultation is supplied, it must belong to that doctor and patient and have the required signed status.

### Diagnostic staff

Center-specific operations check active membership in the diagnostic center associated with the service/request. The center must also satisfy the activation/approval checks used by the relevant helper and serializer.

### Report verifier

Verification requires a membership role accepted by the verifier helper (including owner, center administrator, or report verifier in the shared code). The report preparer cannot verify their own report. Release is permitted only after verification.

### Administrator

Administrative access is supported through Django's staff/admin mechanisms where the relevant view permits it. Exact administrator access should be checked per endpoint; do not assume every staff account bypasses every domain permission.

## 5. Diagnostic workflow and report lifecycle

Conceptually:

```text
Request created
      |
      v
Center accepts / investigation starts
      |
      v
Clinical attachment uploaded
      |
      +------> Optional supported AI analysis
      |                    |
      |                    v
      |             Human review
      |                    |
      v                    v
         Diagnostic report prepared
                    |
                    v
             Submitted for review
                    |
                    v
              Independent verifier
                    |
                    v
                Report released
                    |
                    v
          Diagnostic request completed
```

The report status values confirmed in the model are `SUBMITTED`, `VERIFIED`, and `RELEASED`. The release action checks that the report is already verified, updates `released_at`, and marks the associated diagnostic request completed.

The report preparer and verifier are separate users by enforcement in the verification action.

## 6. AI inference and review architecture

The current integration uses TorchXRayVision DenseNet121 and `densenet121-res224-all` weights. The diagnostic request's service description is checked for a chest X-ray service before this model is used.

The analysis record stores:

- Diagnostic request and source attachment.
- Registered AI model.
- Submitting user.
- Analysis status and timestamps.
- `pathology_scores` JSON.
- `score_semantics` text.
- `model_output` metadata JSON.
- Review status, reviewer, notes, and review timestamp.

The intended report-submission implementation accepts an optional `ai_analysis_id`. It scopes the selected analysis to the same diagnostic request and requires completed analysis, accepted review, a recorded reviewer, and non-empty pathology scores. It then copies a snapshot of model information, source image, scores, semantics, and review information under `findings.ai_assistance`.

The clinician-entered findings and impression remain distinct from AI output. The PDF separates clinical findings, AI decision-support results, and clinical impression.

The score values must not be described as calibrated probabilities or as a diagnosis. A human reviewer must interpret them in context. The model is limited to supported chest X-ray inputs; it must not be applied to DFU images or unrelated modalities.

## 7. Prescription workflow

A prescription has statuses `DRAFT`, `ISSUED`, and `CANCELLED` in the shared model. Prescription items contain medication name, generic name, strength, dosage, route, frequency, duration, quantity, and instructions.

Creation is restricted to an approved doctor and requires an active doctor–patient relationship. If a consultation is selected, it must match the patient and doctor and meet the signed-status condition. At least one medication item is required. The serializer uses a database transaction to create the prescription and its items together.

Only the issuing doctor can issue the draft prescription. Patient list access is restricted to their own issued prescriptions. The PDF generator builds a downloadable representation from the saved prescription and medication items.

## 8. File and PDF handling

Diagnostic attachments use the configured private diagnostic storage. Upload validation checks supported file characteristics (including extension/signature validation in the shared serializer/model implementation). Download endpoints stream files after permission checks rather than revealing a public storage URL.

Diagnostic reports and prescriptions are rendered as PDFs using ReportLab. The PDFs are generated from persisted database records. The source record remains authoritative.

## 9. Data integrity practices

The implementation uses UUID primary keys in core domain models, relational foreign keys, a one-to-one diagnostic report/request relationship, selected `PROTECT` deletion rules, explicit status choices, validation, and database transactions for multi-step operations.

These practices reduce accidental deletion and partial writes. They do not replace database backup, restore testing, audit logging, or a formal data-governance process.

## 10. Current boundaries

This architecture describes the backend functionality established in the shared source and development history. It does not claim a production deployment, frontend application, completed penetration test, formal clinical validation, regulatory approval, full audit trail, or tested disaster-recovery process.
