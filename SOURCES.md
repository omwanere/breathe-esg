# Data Sources & Research Rationale

This document details the real-world research behind our three ingestion streams, the design of our sample datasets, and potential failure modes in live client deployments.

---

## 1. SAP Fuel & Procurement Data

### Real-world Research
* **Transaction Reference**: SAP transaction **MB51** (Material Doc. List) is standard in material management (MM). It displays material movements (goods issues, receipts) filtered by plant (`Werk`), movement type (`Bewegungsart`), and posting date (`Buchungsdatum`).
* **Format Standards**: SAP exports flat lists via Excel or CSV. In German-configured systems, exports utilize the **German localization format**:
  * Date: `DD.MM.YYYY` (e.g. `24.05.2026`).
  * Decimal separator: Comma `,` (e.g. `1234,56`).
  * Thousands separator: Dot `.` (e.g. `1.234,56`).
  * Base Units (`Basismengeneinheit`): German unit codes like `L` (Liters), `KG` (Kilograms), or `STK` (Stück / Pieces).

### Sample Data Design (sap_mb51_export.csv)
We generated **50 rows** featuring:
* Movement types `261` and `201` for fuel consumption (Diesel `MAT-DI-01` and Benzin `MAT-PET-02`), and receipt `101` representing procurement material (`MAT-CO-04`).
* German localized floats (e.g., `1.234,56`).
* **Dirty cases**: 3 rows with unrecognized units (`XYZ`), 2 rows with negative quantities (`-150,00` reflecting inventory corrections), and 1 row with a missing plant code to verify the platform's automatic flagging engine. We also included 5 rows with movement type `311` which are ignored by the parser.

### Production Failure Modes in Live Deployments
* **Text Encoding**: SAP exports often use local system encodings (such as `latin-1` or `cp1252` on German Windows servers) rather than standard UTF-8. To address this, our parser tries decoding using UTF-8 and falls back to `latin-1` on failure.
* **Column Customization**: Users can customize MB51 layouts in SAP. A client might modify or omit headers (e.g. exporting `Posting Date` in English instead of `Buchungsdatum`). Mappings must be updated or headers standardized.

---

## 2. Utility Electricity Data

### Real-world Research
* **Format Reference**: Business portals from vendors like **National Grid**, **EDF Energy**, or **PG&E** offer account invoice billing CSV exports.
* **Format Standards**: CSV lists contain billing period start/end dates, consumption numbers, utility tariffs, meter IDs, and supplier names.

### Sample Data Design (utility_electricity.csv)
We generated **24 rows** representing two meters (UK and US regions) spanning 12 billing cycles in 2023:
* Accounts `AC-UK-99281` (UK average grid factor) and `AC-US-77112` (US-WECC factor).
* Billing cycles crossing calendar boundaries (e.g. Dec 14 to Jan 13).
* Mix of `kWh` and `MWh` units.
* **Dirty cases**: One row with zero consumption (`0.0` kWh), and one row with a 38-day billing period to trigger the platform's anomaly warning flags.

### Production Failure Modes in Live Deployments
* **Invoice Adjustments**: Utility portals often issue correction invoices, creating negative adjustments or duplicate periods.
* **Portal Redesigns**: Portal updates can change CSV header structures overnight, breaking direct text matching.

---

## 3. Corporate Travel Data

### Real-world Research
* **Format Reference**: **SAP Concur** Travel Details reports export employee travel transactions.
* **Format Standards**: Reports include employees, departments, transaction dates (US format `MM/DD/YYYY`), travel modes, transaction amounts in USD, cabin classes (`Y` Economy, `C` Business, etc.), hotel nights, and origin/destination airport IATA codes (e.g., LHR, JFK).

### Sample Data Design (concur_travel_export.csv)
We generated **40 rows** featuring:
* Travel modes: Airfare, Hotel, Car Rental, Rail, Taxi.
* Flights with blank distances (LHR-JFK, BOM-DXB, SIN-SYD) to verify the Great-Circle Haversine distance calculator.
* Mixed booking classes (`Y`, `W`, `C`, `F`) to verify cabin multipliers.
* **Dirty cases**: One flight with origin equal to destination, one expense exceeding the $10,000 threshold, and a ground travel record missing distance.

### Production Failure Modes in Live Deployments
* **IATA Code Issues**: Flight logs may contain non-standard terminal codes or multi-leg flight formats (e.g. LHR-DXB-SIN) that require splitting before lookup.
* **Class Code Differences**: Different travel desks map flight classes to custom letters rather than standard `Y`/`C`/`F` symbols.
