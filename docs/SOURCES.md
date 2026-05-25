# Data Sources & Research Rationale

This document details the real-world research behind each of the three ingestion streams — what format was studied, what the sample data represents, and what would break in a live client deployment.

---

## 1. SAP Fuel & Procurement Data

### Real-World Format Research

**SAP Transaction Referenced**: MB51 (Material Document List). This is the standard SAP Materials Management transaction used by logistics and accounting teams to extract material movement logs. It can be filtered by plant, material, movement type, and posting date, then exported to CSV or Excel.

**Why MB51**: It requires no RFC connectivity or special authorization profiles. Any MM user with basic display access can run MB51 and export results. It is the document that operations teams routinely email to sustainability or finance departments already.

**German Locale Format**: SAP systems configured for German-speaking markets export in German locale by default. This produces:
- Column headers in German: `Buchungsdatum`, `Werk`, `Material`, `Materialkurztext`, `Bewegungsart`, `Menge`, `Basismengeneinheit`, `Buchungsjahr`, `Buchungsperiode`, `Kostenstelle`.
- Decimal separator: comma (`,`) — so 1614.62 appears as `1.614,62`.
- Thousand separator: period (`.`) — creating the `1.234,56` format.
- Date format: `DD.MM.YYYY` — so January 2nd 2024 is `02.01.2024`.
- Unit codes: `L` (Liters), `GAL` (US Gallons), `KG` (Kilograms), `STK` (Stück = Pieces).

**This is not an edge case**. Any SAP system installed on German Windows servers will produce this format without additional configuration. Our parser normalizes all of the above before storing values.

### Sample Data Design (sap_mb51_export.csv)

The sample file contains **50 rows** across three plant codes (`1001`, `1002`, `1003`) covering January–March 2024:

- **Scope 1 rows**: Movement types 261 and 201 for materials `MAT-DI-01` (Diesel) and `MAT-PET-02` (Benzin/Petrol). Units include `L` (liters) and `GAL` (US gallons) to test the UnitConversion lookup.
- **Scope 3 rows**: Movement type 101 for `MAT-ST-03` (Structural Steel) and `MAT-CO-04` (Concrete Mix). These represent upstream procurement, classified as Scope 3.
- **Dirty data included intentionally**:
  - 3 rows with unit `XYZ` (unknown unit) — triggers auto-flagging with reason "Unrecognized unit: XYZ".
  - 2 rows with negative quantity (`-150,00`) — triggers "Negative quantity detected".
  - 1 row with blank `Werk` (plant code) — triggers "Missing plant code".
  - 5 rows with movement type `311` (plant-to-plant transfer) — filtered out by the parser and not ingested.

### What Would Break in a Live Client Deployment

1. **Text encoding**: SAP exports from German Windows servers use `latin-1` or `cp1252` encoding, not UTF-8. Special characters in material descriptions (umlauts: ä, ö, ü) become corrupted if read as UTF-8. Our parser detects encoding errors and falls back to `latin-1`.

2. **Column name customization**: SAP MB51 layouts can be personalized per user. A client's SAP administrator may have renamed columns or added custom fields. `Buchungsdatum` might appear as `Posting Date` in an English-locale system, or be completely absent if the user removed it from their layout.

3. **Custom movement type codes**: Many SAP installations define client-specific movement types in the 900-999 range. Our parser only knows standard SAP movement types. A production deployment would need a configuration mapping per client.

4. **Date format variation**: Date format depends on SAP system locale settings. A UK-configured system might produce `02/01/2024` (ambiguous DD/MM or MM/DD), while a US system produces `01/02/2024`. The parser currently assumes `DD.MM.YYYY` (German standard).

5. **Large file sizes**: Real SAP MB51 exports for large manufacturers can contain 50,000+ rows per month. Our synchronous parser would timeout on a standard Render web dyno. Production requires Celery async processing.

---

## 2. Utility Electricity Data

### Real-World Format Research

**Format Reference**: Business billing portal CSV exports from utility providers including **EDF Energy** (UK), **National Grid** (UK/US), and **PG&E** (California, US). Each provider offers a "Billing History" or "Usage Data" download in CSV format from their online account management portal.

**Why Portal CSV**:
- Facilities management teams already download these files monthly for internal cost allocation.
- The CSV is machine-readable without OCR — 100% accuracy on numeric values.
- Green Button Connect My Data (the US standard utility API) is not available on UK/EU portals and requires OAuth per utility provider.
- PDF invoices require OCR with significant error risk on decimal values (see TRADEOFFS.md).

**Key characteristics of utility billing CSVs**:
- Columns: `account_id`, `meter_id`, `period_start`, `period_end`, `consumption_kwh` or `consumption_mwh`, `tariff_code`, `supplier_name`, `unit_cost`, `total_cost`.
- Billing periods that cross calendar month boundaries (e.g. Dec 14 – Jan 13) — extremely common in UK utility billing.
- Mix of units: some meters billed in kWh, large industrial sites billed in MWh.
- Tariff codes and supplier names present even if not used in carbon calculations — stored in `raw_data` for completeness.

### Sample Data Design (utility_electricity.csv)

The sample file contains **24 rows** covering two meters across 12 monthly billing cycles in 2023:

- **Meter `AC-UK-99281`** (UK site): Uses UK average grid factor (DEFRA 2023, 0.207 kg CO2e/kWh). Billed monthly in kWh. Periods cross calendar boundaries (14th to 13th of following month). Tariff code: `UK-GRID-STD`.
- **Meter `AC-US-77112`** (US site): Uses US average grid factor (EPA eGRID 2022, 0.386 kg CO2e/kWh). Billed in MWh — parser normalizes to kWh by multiplying by 1000 (via UnitConversion table). Tariff code: `US-WECC-GEN`.
- **Dirty data included intentionally**:
  - 1 row with `consumption_kwh = 0.0` — zero consumption flagged as "Zero energy consumption reported — possible meter error".
  - 1 row with a 38-day billing period (July 01 – August 07) — flagged as "Billing period is 38 days (unusual — possible re-bill or meter read correction)".
- All rows classified as `SCOPE_2`.

### What Would Break in a Live Client Deployment

1. **Column name variation across utilities**: EDF uses `consumption_kwh`, National Grid uses `net_consumption`, PG&E uses `usage_kWh`. Same data, completely different column headers. Each new utility provider requires a column mapping update.

2. **Excel format instead of CSV**: Many utility portals export `.xlsx` instead of `.csv`. Our SAP parser handles XLSX — the utility parser currently only handles CSV. Production would need XLSX support added.

3. **Adjustment invoices**: Utility providers issue correction invoices with negative consumption values when meters are re-read. These produce negative `consumption_kwh` rows that must be handled without creating negative emission entries.

4. **Multi-rate tariffs**: Some industrial sites have time-of-use tariffs (peak/off-peak). The consumption data may be split into multiple rows per billing period (peak kWh and off-peak kWh separately), requiring aggregation before storage.

5. **Portal redesigns**: Utility portal CSV formats change without notice during system upgrades. A format change can break the entire ingestion pipeline overnight.

---

## 3. Corporate Travel Data

### Real-World Format Research

**Platform Referenced**: **SAP Concur** Travel & Expense Detail Report. Concur is the dominant enterprise travel and expense management platform globally, used by over 30,000 companies. The Travel Detail report can be exported as CSV from the Concur Analytics or Expense module.

**What the Concur export contains**:
- Employee name, employee ID, department, cost center.
- Transaction date (US format: `MM/DD/YYYY`).
- Expense type: Airfare, Hotel, Car Rental, Rail, Taxi/Rideshare.
- Amount in transaction currency and reporting currency (USD).
- For flights: origin airport (IATA code), destination airport (IATA code), booking class (`Y`/`W`/`C`/`F`), distance in km (often blank — not all Concur configurations export distance).
- For hotels: hotel name, city, number of nights (sometimes absent — only check-in date provided).
- For ground transport: vendor name, city, distance in km or miles (often absent for taxis and car rentals).

**The distance problem**: Concur Travel Detail reports frequently contain origin and destination airport codes but no distance. The distance field is populated only if the booking was made through Concur Travel (not if an expense receipt was submitted manually). Our parser calculates great-circle distance from IATA coordinates when `distance_km` is blank.

### Sample Data Design (concur_travel_export.csv)

The sample file contains **40 rows** covering all three travel categories:

- **Flights (Airfare)**: International routes including LHR→JFK (London–New York), BOM→DXB (Mumbai–Dubai), SIN→SYD (Singapore–Sydney), CDG→ORD (Paris–Chicago). Includes short-haul (LHR→AMS) and long-haul (JFK→NRT). Booking classes cover all four: `Y` (Economy), `W` (Premium Economy), `C` (Business), `F` (First). Some rows have blank `distance_km` to exercise the Haversine IATA lookup. Classified as `SCOPE_3`.
- **Hotels**: International properties across London, Dubai, Singapore, New York. Per room-night emission factor applied. Nights column populated. Classified as `SCOPE_3`.
- **Ground transport**: Car Rental (km-based), Rail (km-based with lower factor than car), Taxi/Rideshare (km-based). Classified as `SCOPE_3`.
- **Dirty data included intentionally**:
  - 1 flight row with origin equal to destination (LHR→LHR) — flagged as "Origin equals destination".
  - 1 expense row with `amount_usd > 10,000` — flagged as "High transaction amount — possible data entry error".
  - 1 ground transport row with blank distance — handled by setting distance to 0 and flagging.

### What Would Break in a Live Client Deployment

1. **Concur report columns are configurable per client**: The standard Travel Detail report column set can be customized by each company's Concur administrator. Column names, column order, and included fields vary between clients on the same platform. "Expense Type" may appear as "Category" at one client and "Transaction Type" at another.

2. **IATA code quality**: Some Concur configurations export city names instead of IATA airport codes (e.g. "London Heathrow" instead of "LHR"). Our IATA coordinate lookup requires standard 3-letter codes. City name matching would require fuzzy search and is significantly less reliable.

3. **Multi-leg flights**: Business travel reports sometimes contain multi-leg itineraries as a single row (e.g. "LHR-DXB-SIN"). Our parser assumes one origin and one destination per row. Multi-leg entries need to be split before IATA lookup.

4. **Hotel nights not always present**: If an employee submits a hotel receipt without specifying the number of nights (only a single date), the per-room-night calculation cannot run. Production requires a fallback or a validation rule enforcing nights count.

5. **Car rental distance not recorded**: Most Concur configurations do not capture distance driven during a car rental — only the total cost. Without distance, per-km emission factors cannot be applied. Production would need odometer-based distance or a km-per-day estimate.
