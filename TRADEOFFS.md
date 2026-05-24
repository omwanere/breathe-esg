# Engineering Tradeoffs

This document details three specific features that were deliberately skipped for this version of the Breathe ESG platform, explaining the technical rationale, the immediate benefits, and the implementation pathway for future development.

---

## Tradeoff 1: File Upload over Real-time Concur/Navan OAuth API Integration

* **Why we skipped it**: Setting up live OAuth 2.0 synchronizations with corporate travel platforms like Concur or Navan requires creating developer profiles on client accounts, setting up secure webhook receiver endpoints in Django, and managing long-lived OAuth refresh tokens in database credentials stores.
* **Short-term benefit**: Implementing a flat-file CSV upload parser eliminated OAuth handshakes and client firewall complications. It allows immediate end-to-end testing and matches what 90% of sustainability teams actually receive from corporate finance departments today.
* **Future implementation pathway**: To support real-time sync, we would configure a Celery beat task to run nightly. This task would loop through data sources, retrieve active tokens, call the `/api/v3.0/common/express-reports` endpoint, parse the travel JSON payload, and save rows using our existing validation schema.

---

## Tradeoff 2: Utility PDF Invoice OCR Parsing

* **Why we skipped it**: Parsing utility invoices from scanned PDFs requires integrating an OCR engine (such as AWS Textract, Azure Document Intelligence, or Tesseract) and building specific layout templates for hundreds of different utility providers. This would introduce significant operational overhead and third-party API dependencies.
* **Short-term benefit**: Restricting the utility pipeline to portal CSVs ensures 100% data ingestion accuracy and avoids errors associated with OCR text boxes (e.g., misreading decimal numbers or missing line items).
* **Future implementation pathway**: We would add an asynchronous PDF processor using AWS Textract or a fine-tuned layout model (e.g. LayoutLM). When a PDF is uploaded, a background task would extract the key-value pairs (Account, Meter, Consumption, Dates), map them to our CSV structure, and feed them into the staging model.

---

## Tradeoff 3: Per-Client Custom Emission Factor UI

* **Why we skipped it**: Large enterprises often negotiate custom grid electricity contracts (market-based emission factors) or burn custom fuel blends with unique carbon values. Building a UI to create, edit, and version custom emission factors would significantly expand the scope of the settings module.
* **Short-term benefit**: Hardcoding standard datasets (DEFRA 2023, EPA eGRID 2022) via database seeds ensures consistent, validated calculations and provides a reliable default calculations baseline.
* **Future implementation pathway**: We would expand the database model to support custom factors per tenant by adding a `tenant` ForeignKey (nullable) to the `EmissionFactor` model. If a tenant-specific factor is defined, the calculation engine would prioritize it over standard global factors. We would then build an Admin Panel tab in the React UI for managing these client-specific values.
