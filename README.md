# Breathe ESG — Data Ingestion Platform

## What this is
A Django REST + React application that ingests carbon emissions 
data from SAP, utility providers, and corporate travel platforms, 
normalizes it, and provides an analyst review dashboard before 
locking data for audit.

## Live URLs
- Frontend: https://<your-frontend>.vercel.app
- Backend API: https://<your-backend>.onrender.com
- Demo login: analyst@demo.com / Demo1234!

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+
- A Supabase account with a project and database URL

### Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add your Supabase DATABASE_URL
python manage.py migrate
python manage.py seed_emission_factors
python manage.py seed_unit_conversions
python manage.py seed_demo_tenant
python manage.py runserver
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env
# .env already has VITE_API_URL=http://localhost:8000
npm run dev
```

Open http://localhost:5173
Log in with analyst@demo.com / Demo1234!

### Load sample data
```bash
# With backend running locally:
# Upload files via the UI at http://localhost:5173/upload
# OR run:
cd backend
python manage.py load_sample_data
```

## Deployment
- Backend: Render Web Service (see build.sh and Procfile)
- Frontend: Vercel (see vercel.json)
- Database: Supabase PostgreSQL

## Documentation
- docs/MODEL.md     — data model and design decisions
- docs/DECISIONS.md — every ambiguity resolved
- docs/TRADEOFFS.md — what was deliberately not built
- docs/SOURCES.md   — real-world format research
