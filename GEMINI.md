# GEMINI.md — NYC 311 Analytics & AI Chatbot System

## 1. Project Overview & Architecture
An automated end-to-end analytics engineering pipeline, cloud data warehouse, and guardrailed natural language AI chatbot with automated visual analytics built on NYC 311 service request data from NYC Open Data.

```
       [NYC Open Data Socrata API]
                    │
                    ▼
     [Local / CI Ingestion Script]
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
 [raw_complaints.json.gz] [DuckDB In-Memory ETL]
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
       [clean_complaints]            [quarantine_complaints]
       (Valid records)               (Broken dates/ZIPs/missing keys)
               │                               │
               └───────────────┬───────────────┘
                               ▼
               [Supabase Cloud Data Warehouse]
                (Public Schema / PostgreSQL 17)
                               │
                               ▼
               [Streamlit AI Chatbot & Visualizer]
               - Natural language questions
               - Gemini 2.5 Flash Text-to-SQL
               - AST/Regex Triple-Layer Read-Only Guardrail
               - Automatic Interactive Visualizations (Bar, Line, Area)
               - Direct Read-Only Postgres Execution
```

---

## 2. Agreed Architectural Invariants & Scope
- **Project Root**: `nyc-311-ai-analysis/` with an isolated Git repository.
- **Data Scope & Retention**: Rolling 30-day window (~80,000–115,000 records, ~50 MB database footprint). An automated pruning routine ensures total storage remains well below Supabase's 500 MB free tier limit.
- **Raw Data Immutability**: Raw API extractions are backed up as compressed JSON (`.json.gz`) in `data/raw/` and are never altered, overwritten, or deleted.
- **Zero Silent Data Loss**: Every malformed or invalid record is routed to a dedicated `quarantine_complaints` table with an explicit `rejection_reason`. Every pipeline execution must mathematically prove:
  $$\text{Raw Count} = \text{Clean Count} + \text{Quarantined Count}$$
- **Cloud Database (Supabase)**: Hosted PostgreSQL database containing a Star Schema (`dim_*`, `fact_*`) and a `quarantine_complaints` table.
- **AI Chatbot & Visualizer (Streamlit + Gemini 2.5 Flash)**:
  1. *Prompt Guardrail*: Schema-constrained system prompt.
  2. *AST/Regex Validator*: Application-level parser blocking all non-`SELECT` statements, multi-statements, and mutation keywords before execution.
  3. *Database Role Security*: Dedicated `readonly_app` PostgreSQL login with `SELECT`-only privileges + read-only RPC function (`execute_readonly_query`).
  4. *Automatic Data Visualization*: Dynamic Altair & Streamlit chart generation (Bar, Line, Area, KPI Cards) based on the shape and semantics of query results.
- **Python Environment**: Standard Python virtual environment (`.venv`) managed via `requirements.txt`.
- **Daily Cloud Automation**: GitHub Actions workflow running on a daily cron schedule (`0 6 * * *`) pushing updates to Supabase without requiring local machine runtime.

---

## 3. Mandatory 4-Gate HITL Analytics Workflow
1. **Gate 1: Read-Only Profiling & Anomaly Audit (`duckdb`)**
   - Inspect raw data using read-only DuckDB SQL.
   - Present Data Health Audit: null rates, cardinality, PK uniqueness, date boundary anomalies, regex/ZIP validity, and proposed cleaning rules.
   - *Approved*.
2. **Gate 2: Transformation, Quarantine & Mathematical Reconciliation (`duckdb` + `excel`)**
   - Execute cleaning rules.
   - Output `clean_complaints.parquet`, `quarantine_complaints.parquet`, and `qa_reconciliation.xlsx`.
   - Present Reconciliation Proof Table proving zero row or metric leakage.
   - *Approved*.
3. **Gate 3: Star Schema Design & Verified Warehouse Load (`supabase`)**
   - Present proposed Star Schema DDL (`dim_*`, `fact_*`, `quarantine_*`) for review.
   - Execute migration, load data, and run post-load row count and metric parity audits.
   - *Approved*.
4. **Gate 4: AI Chatbot, Security Guardrails & Automated Visualization (`streamlit` + `gemini` + `github`)**
   - Build guarded natural language chatbot with Gemini 2.5 Flash text-to-SQL.
   - Triple-layer AST/regex read-only security enforcement.
   - Interactive charting engine automatically rendering visualizations for analytical queries.
   - Daily GitHub Actions ETL automation.

---

## 4. Master Implementation Checklist

### Phase 0: Project Setup & Environment Initialization
- [x] Initialize Git repository in `nyc-311-ai-analysis/` with strict `.gitignore` (`.env`, `data/`, `*.xlsx`, `.venv/`).
- [x] Create Python virtual environment (`.venv`) and install core dependencies.
- [x] Create directory structure (`data/raw/`, `data/clean/`, `data/quarantine/`, `src/etl/`, `src/db/`, `src/chatbot/`, `.github/workflows/`).
- [x] Provision new Supabase project via `supabase` MCP and capture connection strings in `.env`.

### Phase 1: API Extraction & Gate 1 Profiling
- [x] Implement `src/etl/extract.py` to pull 30-day NYC 311 service requests with Socrata pagination.
- [x] Persist compressed raw backup to `data/raw/raw_311_<timestamp>.json.gz`.
- [x] Run read-only DuckDB profiling queries on raw extraction.
- [x] Deliver Gate 1 Data Health Audit report to user.

### Phase 2: Gate 2 Transformation & Mathematical Reconciliation
- [x] Implement `src/etl/transform.py` with validation and quarantine routing logic:
  - Date ordering logic (`created_date <= closed_date`, no future dates).
  - ZIP code sanitization (valid NYC 5-digit regex).
  - Unmapped / missing agency handling.
- [x] Export `data/clean/clean_complaints.parquet` and `data/quarantine/quarantine_complaints.parquet`.
- [x] Generate QA reconciliation audit workbook `qa_reconciliation.xlsx`.
- [x] Deliver Reconciliation Proof Table proving `Raw = Clean + Quarantined`.

### Phase 3: Gate 3 Cloud Warehouse Modeling & Loading (Supabase)
- [x] Present Star Schema DDL specification (`dim_agency`, `dim_complaint_type`, `dim_location`, `dim_calendar`, `fact_complaints`, `quarantine_complaints`).
- [x] Execute schema migrations on Supabase.
- [x] Create `readonly_app` PostgreSQL role and grant `SELECT`-only privileges.
- [x] Implement `src/db/load.py` to load clean dimensions, facts, and quarantine records into Supabase.
- [x] Run automated parity check comparing source Parquet sums vs Supabase table sums.

### Phase 4: Guardrailed AI Chatbot & Automated Visualization (Streamlit + Gemini)
- [x] Implement SQL AST & regex guardrail module (`src/chatbot/guardrail.py`):
  - Enforce single-statement `SELECT`.
  - Reject dangerous keywords (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`).
  - Auto-inject `LIMIT 100` if absent.
- [x] Implement Gemini Text-to-SQL agent (`src/chatbot/agent.py`) using `google-genai` and `gemini-2.5-flash`.
- [x] Build automated visual analytics engine (`src/chatbot/visualizer.py`):
  - Automatic chart type selection (Bar, Line, Area, Scatter, Metric Cards).
  - Interactive chart and data table tabs.
- [x] Build Streamlit interface (`src/chatbot/app.py`):
  - Natural language inquiry chat bar.
  - SQL preview toggle with explanation.
  - Interactive table and chart rendering.
- [x] Execute adversarial injection test suite to verify 100% rejection of unauthorized queries (19/19 passed).

### Phase 5: Daily Automation & Repository Publishing
- [x] Implement GitHub Actions workflow (`.github/workflows/daily_sync.yml`):
  - Scheduled daily execution (6:00 AM UTC).
  - Incremental extraction, transformation, quarantine, and Supabase upsert/pruning.
- [x] Create remote GitHub repository via `github` MCP (`ghady7/nyc-311-ai-analysis`).
- [x] Configure GitHub repository secrets (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `NYC_APP_TOKEN`).
- [x] Push codebase and verify end-to-end pipeline execution in GitHub Actions.
