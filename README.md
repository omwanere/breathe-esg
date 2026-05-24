# Breathe ESG Data Ingestion Platform

Breathe ESG is a full-stack platform designed to ingest carbon footprint data from diverse corporate transactional systems (SAP Material Movements, Utility Power Invoices, Concur Corporate Travel Ledger), normalize units, apply appropriate emission factors, and present a staging portal for analysts to verify, edit, and lock datasets for audit.

---

## 🚀 Local Setup in 4 Commands

Follow these steps to run the application locally (Python and Node.js are required):

```bash
# 1. Clone/Navigate to folder and set up virtual environment
python -m venv venv
venv\Scripts\activate  # On Windows. On Mac/Linux: source venv/bin/activate

# 2. Install backend dependencies & initialize database
pip install -r backend/requirements.txt
python backend/manage.py migrate

# 3. Seed conversion factors, emission factors, and demo workspace
python backend/manage.py seed_unit_conversions
python backend/manage.py seed_emission_factors
python backend/manage.py seed_demo_tenant

# 4. Generate sample files & run the server
python generate_sample_data.py
python backend/manage.py runserver
```

*For the frontend development server, open a separate terminal inside `/frontend` and run:*
```bash
npm install
npm run dev
```

---

## 🐳 Docker Compose Alternative

To launch the multi-container stack containing **Postgres, Redis, Django, and Nginx-hosted React** in one command, run:
```bash
docker-compose up --build
```
Access the application dashboard at `http://localhost:3000`.

---

## 📊 Running Ingestions End-to-End

### 1. Authentication
* Navigate to the dashboard.
* Click **Autofill Demo Login** or enter:
  * **Email/Username**: `analyst@demo.com`
  * **Password**: `Demo1234!`

### 2. Ingestion Upload
Navigate to **Ingest Data** in the sidebar. You will see three panels:
* **SAP MB51**: Drag and drop `sample_data/sap_mb51_export.csv` (contains German decimal formatting, plant codes, movement filters). Click **Ingest File**.
* **Utility electricity**: Upload `sample_data/utility_electricity.csv` (contains kWh/MWh conversion, billing window tracking). Click **Ingest File**.
* **Corporate Travel**: Upload `sample_data/concur_travel_export.csv` (contains blank-distance flights requesting great-circle IATA math, cabin class factors). Click **Ingest File**.

*Note: The platform runs background threads updating ingestion job logs in real time. The status indicators will transition from `PENDING` -> `PROCESSING` -> `COMPLETED`.*

### 3. Review Staging Rows
Navigate to **Review Rows**:
* Filter by **Flagged Only** to inspect validation warnings (e.g. negative quantities, long billing windows, or unrecognized airports).
* Click **Expand** (`v` icon) to view the raw transaction JSON payload, specific warnings, and prospective emission calculations.
* Double-click a row's Quantity to test inline staging edits. Modifying these sets `edited_from_raw = True` and writes an entry in the audit trail.
* Perform single-row **Approvals** or **Rejections** (requires explanation note).
* Select multiple rows and click **Approve Selected** to bulk calculate CO2e metrics.

### 4. Audit Trail and Lock
Navigate to **Audit Export**:
* Review the count of approved staging transactions ready for delivery.
* Click **Export for Audit & Lock**. This downloads a compliance CSV file containing all audited calculations and changes `is_locked` to `True`. Subsequent edits to locked rows are blocked.

---

## 🚀 Free One-Click Backend Deployment (Render)

You can automatically deploy the backend server and its PostgreSQL database for free on Render using this button (make sure to replace `YOUR_GITHUB_REPO_URL` with your pushed GitHub repository link):

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=YOUR_GITHUB_REPO_URL)

Alternatively:
1. Go to the [Blueprints page on Render](https://dashboard.render.com/blueprints).
2. Connect your GitHub repository.
3. Click **Apply** to automatically provision the free database and web server.

---

## 🌐 Live Deployment Placeholders
* **Backend REST API**: [https://breathe-esg-backend.railway.app](https://breathe-esg-backend.railway.app)
* **Frontend Application**: [https://breathe-esg.vercel.app](https://breathe-esg.vercel.app)

