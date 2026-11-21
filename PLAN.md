# Master Implementation & Operations Plan (`PLAN.md`)
## NYC 311 Analytics & AI Chatbot System

---

## 1. Executive Summary & Architecture
An automated end-to-end analytics engineering pipeline, cloud data warehouse, and guardrailed natural language AI copilot built on NYC 311 service request data from NYC Open Data.

- **Cloud Warehouse:** Hosted Supabase PostgreSQL 17 (`nyc-311-warehouse`, project `mcuaamgangsjwczggxgj`).
- **ETL Engine:** DuckDB in-memory transformation, normalization, and quarantine routing.
- **AI Copilot:** Gemini 2.5 Flash Text-to-SQL with triple-layer AST SQL guardrails.
- **Deployment:** Render web service (`app.py`, Streamlit + Plotly visual analytics).
- **Automation:** GitHub Actions daily sync (`.github/workflows/daily_sync.yml`).

---

## 2. Phase Execution Status & Approval Gates

| Phase | Description | Status | Gate Approval |
| :--- | :--- | :--- | :--- |
| **Phase 0** | Setup, Scaffolding & Raw Data Lineage | **COMPLETE** | Approved (`phases/phase_00_report.md`) |
| **Phase 1** | Ingestion & Read-Only DuckDB Profiling | **COMPLETE** | Approved (`phases/phase_01_report.md`) |
| **Phase 2** | Cleaning, Quarantine & Zero Silent Loss Reconciliation | **COMPLETE** | Approved (`phases/phase_02_report.md`) |
| **Phase 3** | Star Schema Warehouse Modeling & Supabase Load | **COMPLETE** | Approved (`phases/phase_03_report.md`) |
| **Phase 4** | Executive Dashboard, Gemini Copilot & AST Guardrail | **COMPLETE** | Approved (`phases/phase_04_report.md`) |
| **Phase 5** | Daily Cloud Sync, Retention & Security Hardening | **COMPLETE** | Approved (`phases/phase_05_report.md`) |

---

## 3. Mathematical Reconciliation Gate (Zero Silent Loss)

$$\text{Raw Count} = \text{Clean Count} + \text{Quarantine Count}$$

| Dataset | Record Count | Reconciliation Equation |
| :--- | :--- | :--- |
| **Raw Extraction** (`data/raw/raw_311_*.json.gz`) | **50,000** | $\text{Raw} = 50,000$ |
| **Clean Records** (`data/clean/clean_complaints.parquet`) | **49,930** | $\text{Clean} = 49,930$ |
| **Quarantined Records** (`data/quarantine/quarantine_*.parquet`) | **70** | $\text{Quarantine} = 70$ |
| **Sum ($\text{Clean} + \text{Quarantine}$)** | **50,000** | $49,930 + 70 = 50,000$ |
| **Mathematical Delta** | **0** | **ZERO ROW LEAKAGE PROVEN** |

---

## 4. Cloud Data Warehouse Star Schema Metrics
**Database:** Supabase PostgreSQL 17 (`nyc-311-warehouse`)

| Table Name | Schema Type | Primary Key | Record Count | Security Status |
| :--- | :--- | :--- | :--- | :--- |
| `dim_agency` | Dimension | `agency_key` (SERIAL) | 16 | RLS Enabled |
| `dim_complaint_type` | Dimension | `complaint_type_key` (SERIAL) | 771 | RLS Enabled |
| `dim_location` | Dimension | `location_key` (SERIAL) | 5,126 | RLS Enabled |
| `dim_calendar` | Dimension | `date_key` (INT) | 365 | RLS Enabled |
| `fact_complaints` | Fact | `unique_key` (BIGINT) | 135,231 | RLS Enabled |
| `quarantine_complaints` | Audit | `quarantine_id` (UUID) | 13,079 | RLS Enabled |

---

## 5. Security & Governance Posture
1. **Supabase Security Advisor Compliance:**
   - Remediated Linter 0028 (`anon_security_definer_function_executable`) and 0029 (`authenticated_security_definer_function_executable`).
   - Function `public.execute_readonly_query(query_text text)` was converted from `SECURITY DEFINER` to `SECURITY INVOKER` with explicit `search_path TO 'public'`.
   - **Active Advisor Lints:** **0 warnings, 0 lints** (Clean security audit).
2. **Triple-Layer AST Guardrails:**
   - Single-statement `SELECT` enforcement.
   - Prohibited SQL keywords (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`, `MERGE`).
   - Public schema table whitelist (`dim_*`, `fact_*`, `quarantine_*`).
   - Dynamic query result cap (`LIMIT 500`).
3. **Storage Retention & Circuit Breakers:**
   - Rolling 30-day retention pruning to preserve Supabase free tier (< 500 MB).
   - Ingestion circuit breaker preventing pruning if new ingestion < 1 record.
