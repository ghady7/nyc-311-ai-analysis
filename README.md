# NYC 311 Executive Analytics & AI Copilot System

A unified, production-ready analytics engineering pipeline, cloud data warehouse, dynamic executive dashboard, and guardrailed Text-to-SQL AI copilot built on NYC 311 service request data from NYC Open Data. Deployable on **Render**.

---

## 1. System Architecture

```
       [NYC Open Data Socrata API]
                    │
                    ▼
     [Daily Cloud ETL Ingestion]
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
 [raw_complaints.json.gz] [DuckDB In-Memory ETL]
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
       [clean_complaints]            [quarantine_complaints]
       (Valid records)               (Data quality audit logs)
               │                               │
               └───────────────┬───────────────┘
                               ▼
               [Supabase Cloud Data Warehouse]
                (Public Schema / PostgreSQL 17)
                               │
                               ▼
        [Unified Streamlit Web Application (Render)]
         ├── Tab 1: Executive KPI Dashboard (Plotly)
         │   ├── In-Database Aggregations (Zero Client Row Leakage)
         │   ├── TTL Caching Layer (ttl=3600s + Manual Invalidation)
         │   └── Interactive Slicers (Date, Borough, Agency, Category, Status)
         └── Tab 2: AI Data Analyst Copilot
             ├── Gemini 2.5 Flash Text-to-SQL
             ├── Triple-Layer AST & Table-Whitelist Guardrail
             └── Automated Plotly Visual Analytics & CSV Export
```

---

## 2. Key Features

### 📊 Executive Dynamic Dashboard (Tab 1)
- **Top KPI Cards with Period-over-Period Deltas:**
  - Total Complaints (`+Delta%` vs prior window)
  - Closure Rate % (`is_closed = true` vs prior period)
  - SLA Compliance Rate % (on-time resolution)
  - Median & Mean Resolution Duration in Hours
- **Visual Analytics Grid (Plotly):**
  - **Volume Trend:** Daily service requests with 7-day rolling average.
  - **Top Complaint Types:** Horizontal bar chart color-coded by category.
  - **Agency Performance Matrix:** Bubble scatter plot (Volume vs. SLA Compliance % vs. Avg Duration).
  - **Geographic Breakdown:** Borough comparison, top 10 incident ZIP codes, and coordinate cluster density map.
  - **Operational Dynamics:** Submission channels (`ONLINE`, `PHONE`, `MOBILE`) and weekday vs. weekend patterns.
- **Performance & Memory Protection:** All aggregations (`GROUP BY`, `COUNT`, `AVG`, `PERCENTILE_CONT`) run directly in PostgreSQL 17. The client never pulls unaggregated fact rows into memory, strictly honoring Render's 512 MB memory limit.

### 💬 AI Data Analyst Copilot (Tab 2)
- **Natural Language Inquiry:** Ask questions in plain English across 123,000+ service requests.
- **Triple-Layer AST Guardrails:** Enforces single-statement `SELECT`, strips markdown, validates public schema table whitelist, blocks DDL/DML mutation keywords, and caps query results at `LIMIT 500`.
- **Automated Visualization Engine:** Intelligently classifies query output dimensions and generates interactive Plotly Bar, Line, or Area charts on the fly.
- **Auditability & Export:** Inspect the verified SQL query with one click and export results directly to CSV.

---

## 3. Directory Layout

```
nyc-311-ai-analysis/
├── app.py                      # Main unified Streamlit application entry point
├── render.yaml                 # Render Blueprint deployment specification
├── requirements.txt            # Pinned production dependencies
├── db/
│   ├── __init__.py
│   ├── connection.py           # Dual-mode HTTPS PostgREST RPC & SQLAlchemy pooler
│   └── queries.py              # In-database PostgreSQL aggregation SQL builders
├── services/
│   ├── __init__.py
│   ├── dashboard_service.py    # Cached aggregation service (ttl=3600s) & filter compiler
│   └── chatbot_service.py      # Gemini 2.5 Flash Text-to-SQL agent & guardrail pipeline
├── components/
│   ├── __init__.py
│   ├── filters.py              # Sidebar filters (Date range, Borough, Agency, Category, Status)
│   ├── kpi_cards.py            # 4 executive KPI cards with delta styling
│   ├── charts.py               # Plotly charts (Trend, Categories, Matrix, Geo, Channels)
│   └── chat_interface.py       # Copilot chat UI, starter questions & auto-visualization
├── src/
│   ├── etl/                    # Extraction & DuckDB transformation logic
│   ├── db/                     # Data loader routines
│   └── chatbot/                # Legacy AST guardrail & test suites
├── tests/
│   └── test_guardrail.py       # Adversarial SQL injection & guardrail test suite
└── .env.example                # Environment variables template
```

---

## 4. Local Quickstart

### Prerequisites
- Python 3.11+
- Virtual environment (`.venv`)

### 1. Installation
```bash
git clone https://github.com/ghady7/nyc-311-ai-analysis.git
cd nyc-311-ai-analysis
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file in the root directory:
```ini
# Supabase PostgreSQL Configuration
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your_supabase_anon_or_service_role_key

# Gemini AI Copilot
GEMINI_API_KEY=your_gemini_api_key

# Optional settings
DASHBOARD_CACHE_TTL=3600
DB_TIMEOUT=30
```

### 3. Run the Application
```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 5. Deployment on Render

This repository includes a `render.yaml` Blueprint for 1-click deployment on **Render**:

1. Link your GitHub repository to Render.
2. Select **New > Blueprint** and choose this repository.
3. In the Render Dashboard under **Environment Variables**, provide:
   - `SUPABASE_URL`: `https://<your_ref>.supabase.co`
   - `SUPABASE_KEY`: Your Supabase API / service role key
   - `GEMINI_API_KEY`: Your Google AI Studio API key
   - `DATABASE_URL`: (Optional) PostgreSQL direct / pooler connection string for SQLAlchemy fallback
   - `PYTHON_VERSION`: `3.11.9`
4. The service will build via `pip install -r requirements.txt` and start with:
   ```bash
   streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
   ```
5. Health checks are automatically handled via `/` and lightweight database connectivity via `/?healthz=true`.

---

## 6. Verification & Automated Testing

Execute the test suites and compile audit:
```bash
# Verify Python syntax across all modules
python -m py_compile app.py db/*.py services/*.py components/*.py

# Execute adversarial SQL guardrail and injection test suite
python -m pytest tests/test_guardrail.py -v
```
