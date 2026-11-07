# MediBridge — Architecture

## 1. Architectural overview

MediBridge is a modular Django REST Framework backend. Identity, organization membership, patient relationships, clinical records, diagnostic operations, AI analysis, and prescription management are separated into Django applications. Requests pass through JWT authentication and endpoint-specific authorization before reaching domain viewsets, serializers, models, and file/PDF services.

```text
 Patient / Doctor / Diagnostic-Center Staff
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
       |            |             +-- Relationships
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
          +-- Services        +-- Prescription records
          +-- Requests        +-- Medication items
          +-- Attachments     +-- Issue workflow
          +-- Reports         +-- Prescription PDF
          +-- AI registry
          +-- AI analyses
          +-- Report PDF
```

This diagram is conceptual. Django models, serializers, viewsets, URL configuration, permission/queryset logic, and the generated OpenAPI schema define the actual implementation.

## 2. Application responsibilities

### `accounts`

Owns the custom user model and identity APIs. Users authenticate by email and use UUID identifiers. The app provides patient and doctor profile models, patient registration, JWT token endpoints, and the current-user endpoint. Public registration is intended for patient accounts.

### `organizations`

Owns diagnostic-center records and center memberships. A membership associates a diagnostic staff user with a diagnostic center and membership role/status. Center approval/activation and active membership are relevant to center-scoped operations.

### `patients`

Owns doctor–patient relationships, consultations, and clinical observations. The relationship lifecycle includes patient initiation, doctor acceptance, and revocation by an authorized participant. Active relationships are used by downstream doctor-access and prescription rules. Consultation and observation serializers/viewsets validate the caller, selected patient, doctor relationship, and relevant consultation state.

### `diagnostics`

Owns diagnostic services, requests, attachments, reports, AI model registration, and AI analyses. It implements request lifecycle actions, private attachment upload/download, chest X-ray analysis, AI review, report submission, independent verification, release, authorized report retrieval, and diagnostic report PDF generation.

### `prescriptions`

Owns prescription records and structured medication items. A prescription is related to a patient and doctor and may reference a consultation. The app implements draft creation, issue action, authorized retrieval, and prescription PDF download.

### `config`

Contains project settings, root URL configuration, ASGI/WSGI entry points, and the PDF renderer used to negotiate `application/pdf` responses through Django REST Framework.

## 3. Domain relationships

Simplified domain map:

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

Important implementation relationships include:

- A diagnostic report is linked one-to-one with its diagnostic request.
- A diagnostic attachment belongs to a diagnostic request.
- An AI analysis references a diagnostic request, source attachment, registered AI model, submitting user, and optional reviewer.
- A prescription references a patient, doctor, and optional consultation.
- Prescription items belong to a prescription and store structured medication/administration details.

## 4. Identity, roles, and authorization

Authorization combines the authenticated user role with resource ownership, patient–doctor relationship state, center membership, and domain workflow state. A UUID is an identifier and does not grant access.

### Patient

Patient report access is restricted to the authenticated patient's own released reports. Patient prescription access is restricted to their own issued prescriptions. Patients can access their authorized clinical records and create supported patient-reported observations for their own record. Diagnostic attachment downloads additionally enforce ownership and report-release rules where applicable.

### Doctor

Doctor report retrieval is available through the report list, detail, and PDF download endpoints when the doctor satisfies the ordering-doctor or active doctor–patient relationship rules. Doctor clinical-record and prescription operations are subject to approval, relationship, ownership, and consultation-state requirements. A consultation supplied for a prescription must match the patient and doctor and meet the signed-consultation requirement.

### Diagnostic staff

Center-specific operations check active membership in the diagnostic center associated with the service or request. The relevant center must satisfy the activation/approval checks used by the endpoint/helper.

### Report verifier

Verification requires a membership role accepted by the verifier logic (including the supported center owner/administrator/report-verifier roles). The report preparer cannot verify their own report. Release is permitted only after verification.

### Administrator

Administrative access is supported through Django staff/admin mechanisms where the relevant view permits it. A staff flag should not be assumed to bypass every domain-level permission; access remains endpoint-specific.

## 5. Patient–doctor and clinical-record workflow

```text
Patient initiates relationship request
                 |
                 v
         Requested doctor accepts
                 |
                 v
          Active relationship
                 |
       +---------+----------+
       |                    |
       v                    v
 Doctor creates         Clinical observations
 consultation           are recorded by an
       |                 authorized participant
       v                    |
 Doctor signs               |
 consultation               |
       |                    |
       +---------+----------+
                 |
                 v
       Patient accesses eligible records
                 |
                 v
     Patient or doctor may revoke relationship
```

Consultations support a draft/signing lifecycle. Patients are intended to retrieve signed consultations, while doctor access is restricted by the applicable relationship and ownership rules. Observations support patient-reported and clinician-recorded data with role-specific access.

A `PatientConsent` model exists, but the current OpenAPI schema does not expose a dedicated consent-management API. Relationship acceptance/revocation should not be described as a complete granular consent-management service.

## 6. Diagnostic workflow and report lifecycle

```text
Diagnostic request created
             |
             v
  Center staff accept / start
             |
             v
    Clinical attachment upload
             |
             +------> Optional supported AI analysis
             |                    |
             |                    v
             |              Human review
             |                    |
             v                    v
        Diagnostic report prepared
                    |
                    v
               Submitted
                    |
                    v
        Independent verification
                    |
                    v
                 Released
                    |
                    v
       Diagnostic request completed
                    |
                    v
     Authorized patient / doctor retrieval
```

The report state values are `SUBMITTED`, `VERIFIED`, and `RELEASED`. A report must be verified before release, and the preparer and verifier must be different users. Release updates the report's release metadata and completes the linked diagnostic request.

A doctor does not need a frontend dashboard for the backend to enforce access: an authorized doctor retrieves visible reports through `GET /api/diagnostics/reports/`, retrieves an individual report through `GET /api/diagnostics/reports/{id}/`, and downloads its PDF through `GET /api/diagnostics/reports/{id}/download/`. The user interface that consumes these endpoints is outside the current project scope.

## 7. AI inference and human-review architecture

The current integration uses TorchXRayVision DenseNet121 with `densenet121-res224-all` weights. The analysis action checks that the diagnostic service is a supported chest X-ray service and that the source attachment is an eligible clinical image belonging to the same request.

The analysis record retains:

- Diagnostic request and source attachment.
- Registered AI model.
- Submitting user.
- Analysis status and timestamps.
- `pathology_scores` JSON.
- `score_semantics` text.
- `model_output` metadata JSON.
- Review status, reviewer, notes, and review timestamp.

The report-submission logic accepts an optional `ai_analysis_id`. The selected analysis must belong to the same request, complete successfully, have an accepted review and recorded reviewer, and contain pathology scores. The backend snapshots model/source information, scores, score semantics, and review information under `findings.ai_assistance`.

Clinician-entered findings and impression remain separate from AI output. Report PDFs distinguish clinical findings, AI decision-support information, and clinical impression. Score values are not calibrated probabilities or diagnoses; a human reviewer must interpret them in clinical context. The model is restricted to supported chest X-ray inputs and must not be used for DFU images or unrelated modalities.

## 8. Prescription workflow

Prescription statuses include `DRAFT`, `ISSUED`, and `CANCELLED`. Prescription items store medication name, generic name, strength, dosage, route, frequency, duration, quantity, and instructions.

Creation requires an approved doctor and an active patient relationship. At least one medication item is required. If a consultation is linked, it must match the patient and doctor and meet the signed-state requirement. Prescription and item creation are handled together by the serializer's transaction. Only the issuing doctor can issue the draft. Patient access is limited to their own issued prescriptions.

## 9. File and PDF handling

Diagnostic attachments use configured private storage. Upload validation checks supported characteristics, including extension/signature checks. Download actions authorize the caller before streaming file content; private storage URLs are not exposed as public links.

Diagnostic reports and prescriptions are generated as PDFs using ReportLab from persisted database records. The source database records remain authoritative. PDF download actions declare a PDF renderer so clients specifying `Accept: application/pdf` can negotiate the response.

## 10. Data-integrity practices

The implementation uses UUID identifiers in core domain models, relational foreign keys, a one-to-one diagnostic report/request relationship, selected `PROTECT` deletion rules, explicit status choices, validation, and database transactions for multi-record operations.

These practices reduce accidental deletion and partial writes. They do not replace backups, restore tests, comprehensive audit logging, or a formal data-governance process.

## 11. Current boundaries

This architecture describes the backend implementation and the local verification results reported for the project. It does not claim a deployed public API service, patient/doctor frontend, automatic report notifications, completed penetration test, formal clinical validation, regulatory approval, complete audit trail, or tested disaster-recovery process.
