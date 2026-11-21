# Phase 04 Report: Guardrailed AI Chatbot & Executive Dashboard

## 1. Phase Objective & Status
- **Objective:** Build an executive visual analytics dashboard in Streamlit with zero client row leakage, alongside a Gemini 2.5 Flash Text-to-SQL copilot protected by a triple-layer AST guardrail and automated Plotly charting.
- **Status:** **COMPLETE & VERIFIED**

---

## 2. Artifacts Created & Modified
| Artifact | Path | Purpose |
| :--- | :--- | :--- |
| **Main Web Application** | `app.py` | Unified Streamlit entry point (Dashboard + Copilot tabs). |
| **AST SQL Guardrail** | `src/chatbot/guardrail.py` | Regex/AST parser enforcing single `SELECT`, keyword rejection, table whitelist. |
| **Gemini SQL Copilot** | `services/chatbot_service.py` | Schema-grounded text-to-SQL agent using `gemini-2.5-flash`. |
| **Query Engine** | `db/queries.py` | Parameterized in-database aggregation SQL queries. |
| **Dashboard Service** | `services/dashboard_service.py` | TTL cached data fetcher (ttl=3600s). |
| **UI Components** | `components/` | Visual components (Filters, KPI cards, Plotly charts, Chat). |
| **Adversarial Test Suite** | `tests/test_guardrail.py` | 19 security test cases testing SQL injection evasion. |

---

## 3. Security Guardrail Audit (AST & Lexical Parser)
The triple-layer guardrail was subjected to adversarial security injection vectors:

| Injection Vector / Test Case | Guardrail Action | Test Status |
| :--- | :--- | :--- |
| Single-statement `SELECT ...` | Pass with `LIMIT` injection / ceiling cap | **PASS** |
| Multi-statement semicolon injection (`SELECT 1; DROP TABLE ...`) | **REJECTED** (`MULTIPLE_STATEMENTS`) | **PASS** |
| DDL Mutation (`DROP`, `ALTER`, `TRUNCATE`, `CREATE`) | **REJECTED** (`PROHIBITED_KEYWORD`) | **PASS** |
| DML Mutation (`DELETE`, `UPDATE`, `INSERT`, `MERGE`) | **REJECTED** (`PROHIBITED_KEYWORD`) | **PASS** |
| System Catalog Exfiltration (`pg_shadow`, `auth.users`, `vault.secrets`) | **REJECTED** (`UNAUTHORIZED_CATALOG`) | **PASS** |
| Comment evasion attack (`SELECT * FROM fact -- DROP TABLE`) | **SANITIZED & REJECTED** | **PASS** |
| Excessive Row Fetch (`SELECT * ... LIMIT 50000`) | **CAPPED** at `LIMIT 500` | **PASS** |

---

## 4. Verification Commands
```powershell
# Run adversarial guardrail & dashboard test suite
.\.venv\Scripts\pytest tests/ -v
# Run live sample analytical queries
.\.venv\Scripts\python scripts/test_sample_queries.py
```
