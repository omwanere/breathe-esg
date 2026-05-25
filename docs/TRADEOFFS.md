# Engineering Tradeoffs

This document describes three features that were deliberately not built in this version of the Breathe ESG platform. For each: what was omitted, why the omission was the correct engineering decision for this stage, and what the complete production implementation would require.

---

## Tradeoff 1: Live OAuth API Integration (Concur / Navan) Not Built

### What was NOT built
A live synchronization integration with corporate travel platforms (SAP Concur, Navan/TripActions, Amex GBT) via their published REST APIs. In production, such an integration would automatically pull new travel expenses into the platform nightly or on-demand, without requiring analysts to manually export and upload CSV files.

### Why it was deliberately skipped
Establishing live OAuth 2.0 connections to corporate Concur instances requires:
- Registering a developer application with SAP Concur's developer portal per deployment environment.
- Client company IT security teams approving third-party OAuth application access to their Concur tenant — a process that takes 4–12 weeks in enterprise environments.
- Managing long-lived OAuth refresh tokens securely in the backend database, with rotation and revocation handling.
- Building a Celery async worker that polls the Concur v3.0 API (`/api/v3.0/common/extract`) on a schedule and handles pagination, rate limits, and partial failure.

None of this is buildable in prototype timescale without client Concur admin credentials. More importantly, 90% of sustainability teams already receive their travel data as a CSV from the finance department each month — the CSV upload covers the actual operational workflow without requiring OAuth infrastructure.

### What the real solution would look like
A `ConcurIntegration` model per tenant storing encrypted OAuth tokens. A Celery beat task running nightly that calls the Concur Extract API, maps the JSON response fields to our CSV column schema, and feeds rows through the existing travel parser. The UI would show a "Connected" status and a "Last synced" timestamp instead of a file upload zone.

---

## Tradeoff 2: PDF Utility Invoice Parsing Not Built

### What was NOT built
Direct ingestion of scanned or digital PDF utility invoices. In the real world, many facilities teams only have access to PDF bills — some utilities do not offer portal CSV exports for business accounts, and paper-based billing is still common in smaller markets.

### Why it was deliberately skipped
Parsing utility invoices from PDFs requires:
- An OCR engine (AWS Textract, Azure Document Intelligence, or Tesseract) to extract text and key-value pairs from the document.
- Layout-aware parsing logic specific to each utility provider — the position of "Total kWh" on an EDF invoice is completely different from its position on a National Grid or PG&E invoice.
- A validation layer to catch OCR transcription errors on numeric fields (OCR commonly misreads `1,614` as `1,614` but also confuses `0` with `O` and `1` with `l` in invoice fonts).
- Third-party API cost and latency per PDF processed.

OCR errors on consumption figures directly corrupt carbon calculations — a misread `1,614 kWh` that becomes `1,614,000 kWh` would produce a 1000× overstatement in Scope 2 emissions. The portal CSV export eliminates this risk entirely and covers the majority of enterprise facilities teams who already use online billing portals.

### What the real solution would look like
An async PDF processing pipeline: PDF upload triggers a Celery task, AWS Textract or a fine-tuned LayoutLM model extracts key-value pairs from the invoice, a per-provider template maps extracted fields to our CSV schema, and a human-review step flags any row where OCR confidence is below a threshold. The analyst reviews and confirms extracted values before they enter the staging table.

---

## Tradeoff 3: Per-Tenant Custom Emission Factor Configuration UI Not Built

### What was NOT built
A self-service UI for tenant administrators to create, edit, and version their own emission factors. In production, large enterprise clients frequently have:
- Renewable energy contracts with market-based Scope 2 factors different from the national grid average.
- Custom fuel blends (biodiesel mixes) with carbon intensities not covered by DEFRA standard factors.
- Internally negotiated logistics factors for specific freight carriers.

### Why it was deliberately skipped
Building a factor configuration UI requires:
- Extending the `EmissionFactor` model to support a nullable `tenant` FK (global factors have no tenant; custom factors belong to a specific tenant).
- A priority resolution system: if a tenant-specific factor exists for `activity_type + region + unit`, use it; otherwise fall back to the global DEFRA/EPA factor.
- Version history on factors — if a client updates their renewable energy contract mid-year, historical approved rows must retain the factor that was applied at approval time (already solved by storing `emission_factor_used` on each row).
- A React admin panel tab with form validation, factor preview calculations, and an audit trail for factor changes.

For this prototype, seeding the DEFRA 2023 and EPA eGRID 2022 factors via management commands provides consistent, validated defaults that cover the demo data correctly. The calculation engine already reads from the `EmissionFactor` database table rather than hardcoding values, so adding custom factors requires only the model extension and UI — not a parser rewrite.

### What the real solution would look like
A `TenantEmissionFactor` model extending `EmissionFactor` with a `tenant` FK and `valid_from` / `valid_to` date range. The calculation engine performs a lookup: `TenantEmissionFactor.objects.filter(tenant=row.tenant, activity_type=..., valid_from__lte=row.activity_date, valid_to__gte=row.activity_date).first()` and falls back to the global `EmissionFactor` table if no tenant-specific factor exists. A Settings tab in the React UI provides the CRUD interface with a live preview showing the impact on pending rows.
