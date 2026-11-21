# Phase 05 Report: Daily Automation & Security Hardening

## 1. Phase Objective & Status
- **Objective:** Deploy daily cloud synchronization via GitHub Actions, configure Render hosting, enforce rolling 30-day retention policies, and remediate Supabase Security Advisor lints (0028 & 0029) on `public.execute_readonly_query`.
- **Status:** **COMPLETE & VERIFIED**

---

## 2. Artifacts Created & Modified
| Artifact | Path | Purpose |
| :--- | :--- | :--- |
| **Daily Sync Workflow** | `.github/workflows/daily_sync.yml` | Daily UTC 06:00 cron pipeline in GitHub Actions. |
| **Retention Policy** | `src/etl/retention.py` | 30-day rolling window pruner and autovacuum executor. |
| **Security Migration** | `sql/002_fix_execute_readonly_query_security_invoker.sql` | DDL migration converting RPC to `SECURITY INVOKER`. |
| **Database Connector** | `db/connection.py` | Updated PostgREST RPC invoker docs and execution layer. |

---

## 3. Supabase Security Advisor Linter Remediation (0028 & 0029)

### Issue Diagnosis
- **Linter Rule 0028:** `anon_security_definer_function_executable` (WARN)
- **Linter Rule 0029:** `authenticated_security_definer_function_executable` (WARN)
- **Root Cause:** In PostgreSQL/Supabase, functions in `public` with `SECURITY DEFINER` run as superuser `postgres`. PostgREST exposes public functions as RPC endpoints (`/rest/v1/rpc/*`). Because permissions defaulted to `PUBLIC`, anonymous internet clients possessing the public `anon` key could invoke dynamic SQL execution with superuser privileges.

### Implemented Resolution
1. **Replaced `SECURITY DEFINER` with `SECURITY INVOKER`:**
   - Modified `public.execute_readonly_query(query_text text)` so it executes strictly under the database privileges of the caller (`anon`, `authenticated`, `service_role`, or `readonly_app`).
   - Completely eliminated privilege escalation to superuser `postgres`.
   - The function's internal multi-statement check, regex keyword blacklist, internal schema protection, and 30-second `statement_timeout` remain actively enforced.
2. **Audit Verification:**
   - Queried Supabase Security Advisor API via `supabase.get_advisors(project_id="mcuaamgangsjwczggxgj", type="security")`.
   - **Result:** `{"result": {"lints": []}}` (**0 warnings, 0 lints**).
3. **Application Verification:**
   - Tested live PostgREST HTTPS queries (`scripts/test_sample_queries.py`).
   - Ran 79 automated pytest tests (`tests/`). All 79 passed with zero errors.

---

## 4. Verification Commands
```powershell
# 1. Run full test suite
.\.venv\Scripts\pytest tests/ -v

# 2. Check live sample queries
.\.venv\Scripts\python scripts/test_sample_queries.py

# 3. Check live table counts
.\.venv\Scripts\python scripts/check_live_counts.py
```
