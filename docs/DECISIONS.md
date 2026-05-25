# Architectural Decisions Document (ADD)

This document explains every significant technical choice made during the implementation of the Breathe ESG Data Ingestion Platform — what was decided, why, what was explicitly rejected, and what we would clarify with the Product Manager before a production rollout.

---

## 1. SAP Ingestion

### Decision: Flat File CSV/XLSX (MB51 Export) over IDoc, OData, or BAPI

**What was chosen**: CSV/XLSX flat file exported from SAP transaction MB51 (Material Document List).

**Why flat file**:
- SAP ERP systems sit behind strict corporate firewalls. RFC/OData connections require network-level access (VPN, SAP Router, firewall rule exceptions) and months of enterprise IT security approvals per client.
- IDoc (Intermediate Documents) is a machine-to-machine SAP messaging format designed for ERP-to-ERP integration. It requires a configured IDoc receiver port on the receiving system — not appropriate for a CSV ingestion prototype.
- BAPI (Business Application Programming Interface) calls require a licensed SAP RFC SDK and a dedicated technical user with specific authorization roles. Again, inappropriate without deep SAP client access.
- MB51 is a standard transaction accessible to any MM (Materials Management) user. Accounting and operations teams already use it to generate reports. Scheduling a CSV export via the SAP job scheduler (SM36) requires no additional permissions.

**What was explicitly ignored**: Real-time RFC/OData/IDoc integration. This is documented in TRADEOFFS.md.

---

### Decision: Movement Types 261, 201, 101 Included; All Others Excluded

**What was chosen**: Filter rows where `Bewegungsart` (movement type) is 261, 201, or 101.

**Why these three**:
- `261` (Goods Issue to Production Order): Direct fuel/material consumption against a production order. This is the primary Scope 1 consumption event in manufacturing.
- `201` (Goods Issue to Cost Center): Direct consumption assigned to a cost center — covers fleet fuel drawn from on-site tanks.
- `101` (Goods Receipt for Purchase Order): Procurement of materials from external suppliers. Scope 3 upstream.

**What was excluded and why**:
- `311` (Transfer Posting Plant-to-Plant): Inventory moving between plants — not consumption, no emission event.
- `561` (Initial Stock Entry): Opening balance entry for new plants — not a transaction, just a setup record.
- `122` (Return Delivery to Vendor): Reversal of a procurement — negative Scope 3 event but too ambiguous to automatically classify.
- Custom movement types (client-specific): Unknown to the platform without client-side documentation. Excluded and would require PM clarification per client.

---

### Decision: German Column Headers Are Not Optional — They Are The Real SAP Format

SAP systems configured in German-speaking countries (Germany, Austria, Switzerland) export column headers in German. This is not an edge case — it is the default output from MB51 on a German-locale SAP system. Our parser reads only German column names: `Buchungsdatum`, `Werk`, `Materialkurztext`, `Menge`, `Basismengeneinheit`, `Bewegungsart`, `Kostenstelle`. An English-locale SAP export would require a separate column mapping and is documented as a known production failure mode in SOURCES.md.

---

## 2. Utility Electricity Ingestion

### Decision: Portal CSV Export over PDF OCR or Green Button API

**What was chosen**: CSV download from utility billing portal (EDF, PG&E, National Grid).

**Why CSV over PDF**:
- PDF parsing requires an OCR engine (AWS Textract, Azure Document Intelligence, or Tesseract). OCR introduces transcription errors on numeric values — a misread decimal is catastrophic for carbon reporting. The portal CSV is machine-readable without OCR.
- PDF invoice layouts vary per utility provider and can change without notice with portal redesigns.

**Why CSV over Green Button API**:
- Green Button Connect My Data is a US standard (ESPI protocol). It is not available on UK, EU, or Asian utility portals.
- Even where available, it requires OAuth authorization with each utility provider per client — a significant onboarding process.
- Facilities teams already download CSV exports as part of their monthly billing workflow. The analyst uploads the same file they already have.

**What was explicitly ignored**: PDF parsing and live API polling. See TRADEOFFS.md.

---

### Decision: Billing Periods Stored as period_start / period_end; Activity Date = Midpoint

**What was stored**: `period_start` and `period_end` are stored separately on every utility row, preserving the exact billing interval. `activity_date` is set to the midpoint of the billing period.

**Why**: Utility invoices commonly cover non-calendar periods (e.g. 14 December to 13 January). Storing only a single month would lose information about which days the consumption covered. Midpoint allocation is the standard approach recommended by GHG Protocol for billing periods that cross month boundaries — the activity date falls in the month representing the bulk of consumption.

---

## 3. Corporate Travel Ingestion

### Decision: SAP Concur "Travel & Expense Detail" Report CSV over Navan API or OAuth

**What was chosen**: CSV export from the Concur Travel & Expense Detail report.

**Why Concur CSV over live API**:
- Concur's API (SAP Concur API v3.0) requires corporate admin OAuth credentials and a registered developer app per client. Client security departments routinely block third-party OAuth registrations during initial ESG onboarding.
- Finance teams already generate Concur Travel Detail reports for expense reconciliation. Analysts receive these CSV files from finance monthly — no new process required.

**What was explicitly ignored**: Live OAuth integration, Navan (formerly TripActions) API, Amex GBT data feeds. See TRADEOFFS.md.

---

### Decision: Great-Circle Distance (Haversine) over Actual Airline Route Distance

**What was chosen**: Haversine formula applied to IATA airport coordinates.

**Why great-circle over actual route**:
- Actual flight routes are variable — weather diversions, air traffic holdings, and routing agreements change paths daily. Using actual routes would produce inconsistent results for the same city pair across different trips.
- DEFRA and the GHG Protocol both mandate great-circle distance as the standardized baseline for flight emissions calculations. Using it ensures our results match what a third-party auditor would calculate independently.
- IATA airport coordinate lookups are bundled as a JSON fixture in the parser. This covers the 300 most-used international airports.

**Limitation acknowledged**: Great-circle distance underestimates actual flight distance by approximately 5-10% due to route inefficiencies. DEFRA accounts for this with the Radiative Forcing Index (RFI) multiplier — a future enhancement.

---

### Decision: Cabin Class Multipliers — DEFRA Standard

**What was chosen**: Economy (Y) = 1.0×, Premium Economy (W) = 1.6×, Business (C) = 2.0×, First (F) = 2.4×.

**Why**: Business and first class seats occupy significantly more physical floor space per passenger on an aircraft. A business class seat is approximately 4–6× larger in area than an economy seat. The DEFRA conversion factors translate this space premium into a per-passenger CO2e premium. These are the published DEFRA 2023 multipliers.

---

### Decision: Emission Factor Source — DEFRA 2023 (Primary) + EPA eGRID 2022 (US Electricity)

**What was chosen**: DEFRA (UK) Greenhouse Gas Conversion Factor Repository 2023 as the global default. EPA eGRID 2022 for US-region electricity.

**Why DEFRA**: DEFRA publishes the most comprehensive, publicly audited, and internationally recognized set of carbon conversion factors. It covers fuels, electricity, freight, travel, hotels, and materials in a single dataset, updated annually. It is widely accepted in GHG Protocol-aligned reports.

**Why EPA eGRID for US electricity**: The US national grid is fragmented into regional sub-grids with significantly different carbon intensities (e.g. WECC in the Western US is cleaner than SERC in the Southeast). EPA eGRID provides region-specific electricity factors. For simplicity, we use the US national average from eGRID 2022.

**What was explicitly ignored**: Ecoinvent (commercial, requires license), IPCC AR6 factors (suitable for national inventory, not corporate accounting), custom client-uploaded factors (future feature — see TRADEOFFS.md).

---

## 4. Data Model Decisions

### Decision: Row-Level Tenant FK over Schema-Per-Tenant

**What was chosen**: Every table carries a `tenant` ForeignKey. All views filter by `request.user.tenant`.

**Why**: Schema-per-tenant (e.g. django-tenants package) requires dynamic database connection routing, a shared schema for cross-tenant reference tables, and per-tenant migration management. For a prototype with fewer than 50 tenants, row-level isolation is simpler to deploy, easier to query, and produces no measurable performance difference.

**What was explicitly ignored**: Database-per-tenant (prohibitively expensive at prototype stage), schema-per-tenant (operational complexity not justified at current scale).

---

### Decision: Audit Lock on Export, Not on Approval

**What was chosen**: `is_locked = True` is set when a row is exported for audit, not when it is approved.

**Why**: Approval is an analyst action — it can be reversed (a row can be re-reviewed if an error is found before export). Locking is the final irreversible action that commits the row to the audit record. Once the auditor receives the CSV, the data underneath it must not change. Separating "approved" from "locked" preserves a staging window between analyst approval and external audit submission.

---

## 5. Questions for the Product Manager

Before a production rollout, these questions must be answered:

1. **SAP Plant Code Resolution**: Are SAP plant code translations (Werk → Location) maintained centrally by Breathe ESG, or does each client configure their own mapping? Currently we store the raw Werk code in `location` — a lookup table per tenant would require a new model.

2. **Analyst Edit Permissions**: Can analysts edit `parsed_quantity` and `parsed_unit` directly on staging rows? Or should all edits require sign-off from a senior manager? Currently any authenticated analyst can edit any pending row for their tenant.

3. **Locked Row Override**: Should locked rows ever be unlockable? If a material error is found post-export, who has the authority to unlock and re-approve — only a superuser? Is there a re-lock audit trail required?

4. **Multi-Currency Travel Expenses**: Concur logs amounts in local transaction currency. Should the backend convert to a reporting currency (USD/GBP) at ingest time using a live rate API, or does the client's finance team provide pre-converted CSVs?

5. **Re-upload Deduplication**: If a client uploads the same Concur export twice, should the system skip duplicate rows, overwrite existing ones, or create duplicate entries? Currently it creates duplicates — a fingerprint-based deduplication policy is needed.
