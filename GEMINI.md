# GEMINI.md — NYC 311 Analytics & AI Chatbot System

## 1. Project Overview & Architecture
An automated end-to-end analytics engineering pipeline, cloud data warehouse, Power BI reporting suite, and guardrailed natural language AI chatbot built on NYC 311 service request data from NYC Open Data.

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
                (Public Schema / PostgreSQL)
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
 [Power BI Desktop Dashboard]          [Streamlit Chatbot UI]
 - Ticket Ops & SLA Delays              - Natural language questions
 - Pipeline Health & Quarantine         - Gemini 2.5 Flash Text-to-SQL
                                        - AST/Regex Read-Only Guardrail
                                        - Read-Only Postgres Execution
```

---

## 2. Agreed Architectural Invariants & Scope
- **Project Root**: `nyc-311-ai-analysis/` with an isolated Git repository.
- **Data Scope & Retention**: Rolling 30-day window (~80,000–100,000 records, ~50 MB database footprint). An automated pruning routine ensures total storage remains well below Supabase's 500 MB free tier limit.
- **Raw Data Immutability**: Raw API extractions are backed up as compressed JSON (`.json.gz`) in `data/raw/` and are never altered, overwritten, or deleted.
- **Zero Silent Data Loss**: Every malformed or invalid record is routed to a dedicated `quarantine_complaints` table with an explicit `rejection_reason`. Every pipeline execution must mathematically prove:
  $$\text{Raw Count} = \text{Clean Count} + \text{Quarantined Count}$$
- **Cloud Database (Supabase)**: Hosted PostgreSQL database containing a Star Schema (`dim_*`, `fact_*`) and a `quarantine_complaints` table.
- **AI Chatbot Guardrails (Streamlit + Gemini 2.5 Flash)**:
  1. *Prompt Guardrail*: Schema-constrained system prompt.
  2. *AST/Regex Validator*: Application-level parser blocking all non-`SELECT` statements, multi-statements, and mutation keywords before execution.
  3. *Database Role Security*: Dedicated `readonly_app` PostgreSQL login with `SELECT`-only privileges.
- **Power BI Connectivity**: PostgreSQL connector using **Import Mode** for optimal DAX calculation performance, scheduled refresh, and sub-second visual responsiveness.
- **Python Environment**: Standard Python virtual environment (`.venv`) managed via `requirements.txt`.
- **Daily Cloud Automation**: GitHub Actions workflow running on a daily cron schedule (`0 6 * * *`) pushing updates to Supabase without requiring local machine runtime.

---

## 3. Mandatory 4-Gate HITL Analytics Workflow
Every analytical layer in this project adheres to the user-enforced 4-Gate Human-in-the-Loop workflow. Progression to write or mutation steps requires explicit user approval at each gate.

1. **Gate 1: Read-Only Profiling & Anomaly Audit (`duckdb`)**
   - Inspect raw data using read-only DuckDB SQL.
   - Present Data Health Audit: null rates, cardinality, PK uniqueness, date boundary anomalies, regex/ZIP validity, and proposed cleaning rules.
   - *Gate Stop*: Requires explicit `APPROVE GATE 1` before writing transformations.
2. **Gate 2: Transformation, Quarantine & Mathematical Reconciliation (`duckdb` + `excel`)**
   - Execute cleaning rules.
   - Output `clean_complaints.parquet`, `quarantine_complaints.parquet`, and `qa_reconciliation.xlsx`.
   - Present Reconciliation Proof Table proving zero row or metric leakage.
   - *Gate Stop*: Requires explicit `APPROVE GATE 2` before schema creation or cloud loading.
3. **Gate 3: Star Schema Design & Verified Warehouse Load (`supabase`)**
   - Present proposed Star Schema DDL (`dim_*`, `fact_*`, `quarantine_*`) for review.
   - After DDL approval, execute migration, load data, and run post-load row count and metric parity audits.
   - *Gate Stop*: Requires explicit `APPROVE GATE 3` before semantic modeling or Git pushes.
4. **Gate 4: Semantic Layer & DAX Engineering (`powerbi` + `github`)**
   - Present data model relationships, hidden technical keys, and DAX measure specifications in a dedicated `_Measures` table.
   - Verify DAX calculations and build the two designated dashboard pages.
   - Commit and push reproducible code via local Git / GitHub MCP.

---

## 4. Master Implementation Checklist

### Phase 0: Project Setup & Environment Initialization
- [ ] Initialize Git repository in `nyc-311-ai-analysis/` with strict `.gitignore` (`.env`, `data/`, `*.xlsx`, `.venv/`).
- [ ] Create Python virtual environment (`.venv`) and install core dependencies (`duckdb`, `google-genai`, `streamlit`, `psycopg2-binary`, `sqlalchemy`, `requests`, `pandas`, `openpyxl`, `python-dotenv`).
- [ ] Create directory structure (`data/raw/`, `data/clean/`, `data/quarantine/`, `src/etl/`, `src/db/`, `src/chatbot/`, `.github/workflows/`, `powerbi/`).
- [ ] Provision new Supabase project via `supabase` MCP and capture connection strings in `.env`.

### Phase 1: API Extraction & Gate 1 Profiling
- [ ] Implement `src/etl/extract.py` to pull 30-day NYC 311 service requests with Socrata pagination.
- [ ] Persist compressed raw backup to `data/raw/raw_311_<timestamp>.json.gz`.
- [ ] Run read-only DuckDB profiling queries on raw extraction.
- [ ] Deliver Gate 1 Data Health Audit report to user.
- [ ] **HOLD FOR `APPROVE GATE 1`**.

### Phase 2: Gate 2 Transformation & Mathematical Reconciliation
- [ ] Implement `src/etl/transform.py` with validation and quarantine routing logic:
  - Date ordering logic (`created_date <= closed_date`, no future dates).
  - ZIP code sanitization (valid NYC 5-digit regex).
  - Unmapped / missing agency handling.
- [ ] Export `data/clean/clean_complaints.parquet` and `data/quarantine/quarantine_complaints.parquet`.
- [ ] Generate QA reconciliation audit workbook `qa_reconciliation.xlsx` using `excel` MCP.
- [ ] Deliver Reconciliation Proof Table proving `Raw = Clean + Quarantined`.
- [ ] **HOLD FOR `APPROVE GATE 2`**.

### Phase 3: Gate 3 Cloud Warehouse Modeling & Loading (Supabase)
- [ ] Present Star Schema DDL specification (`dim_agency`, `dim_complaint_type`, `dim_location`, `dim_calendar`, `fact_complaints`, `quarantine_complaints`).
- [ ] User confirms DDL.
- [ ] Execute schema migrations on Supabase.
- [ ] Create `readonly_app` PostgreSQL role and grant `SELECT`-only privileges.
- [ ] Implement `src/db/load.py` to load clean dimensions, facts, and quarantine records into Supabase.
- [ ] Run automated parity check comparing source Parquet sums vs Supabase table sums.
- [ ] **HOLD FOR `APPROVE GATE 3`**.

### Phase 4: Gate 4 Power BI Semantic Modeling
- [ ] Document Power BI model design:
  - 1-to-many single-direction relationships from `dim_*` to `fact_complaints`.
  - Independent/disconnected relationship for `quarantine_complaints`.
  - Hidden foreign keys and surrogate IDs.
  - Centralized `_Measures` table formulas (Total Complaints, Resolution Rate %, Avg Resolution Hours, Quarantined Count, Pass Rate %).
- [ ] Connect Power BI Desktop via PostgreSQL Import Mode.
- [ ] Construct Page 1: **Ticket Operations & SLA Delays**.
- [ ] Construct Page 2: **Pipeline Health & Data Quarantine**.

### Phase 5: Guardrailed AI Chatbot (Streamlit + Gemini 2.5 Flash)
- [ ] Implement SQL AST & regex guardrail module (`src/chatbot/guardrail.py`):
  - Enforce single-statement `SELECT`.
  - Reject dangerous keywords (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`).
  - Auto-inject `LIMIT 100` if absent.
- [ ] Implement Gemini Text-to-SQL agent (`src/chatbot/agent.py`) using `google-genai` and `gemini-2.5-flash`.
- [ ] Build Streamlit interface (`src/chatbot/app.py`):
  - User query input.
  - SQL preview toggle with explanation.
  - Interactive table rendering and KPI summary.
- [ ] Execute adversarial injection test suite to verify 100% rejection of unauthorized queries.

### Phase 6: Daily Automation & Repository Publishing
- [ ] Implement GitHub Actions workflow (`.github/workflows/daily_sync.yml`):
  - Scheduled daily execution (6:00 AM UTC).
  - Incremental extraction, transformation, quarantine, and Supabase upsert/pruning.
- [ ] Create remote GitHub repository via `github` MCP.
- [ ] Configure GitHub repository secrets (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `NYC_APP_TOKEN`).
- [ ] Push codebase and verify end-to-end pipeline execution in GitHub Actions.
