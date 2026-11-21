# Phase 03 Report: Cloud Warehouse Modeling & Star Schema Load

## 1. Phase Objective & Status
- **Objective:** Deploy 3NF/Star Schema DDL to Supabase Cloud PostgreSQL 17 (`dim_*`, `fact_*`, `quarantine_*`), enforce primary/foreign keys, configure connection poolers, and load clean data with full referential integrity.
- **Status:** **COMPLETE & VERIFIED**

---

## 2. Artifacts Created & Modified
| Artifact | Path | Purpose |
| :--- | :--- | :--- |
| **Database Loader** | `src/db/load.py` | Staging, dimension upsert, and fact ingestion pipeline. |
| **Database Connection** | `db/connection.py` | Dual-mode HTTPS PostgREST RPC and SQLAlchemy pooled execution. |
| **DDL Schema Definitions** | `src/db/load.py` & Supabase | Star schema table definitions, indexes, and RLS policies. |

---

## 3. Schema Architecture & Physical Row Counts
Cloud Data Warehouse: **Supabase PostgreSQL 17 (`nyc-311-warehouse`)**

| Table Name | Schema Type | Primary Key | Live Record Count | Storage Role |
| :--- | :--- | :--- | :--- | :--- |
| `dim_agency` | Dimension | `agency_key` (SERIAL) | 16 | Agency code, name, and SLA standards. |
| `dim_complaint_type` | Dimension | `complaint_type_key` (SERIAL) | 771 | Complaint category and descriptive descriptor. |
| `dim_location` | Dimension | `location_key` (SERIAL) | 5,126 | Borough, ZIP code, latitude, and longitude. |
| `dim_calendar` | Dimension | `date_key` (INT) | 365 | Temporal attributes, day of week, weekend flags. |
| `fact_complaints` | Fact | `unique_key` (BIGINT) | 135,231 | Central transactional service request measurements. |
| `quarantine_complaints` | Audit | `quarantine_id` (UUID) | 13,079 | Quarantined malformed records with audit lineage. |

---

## 4. Referential Integrity & Security Audits
- **Primary / Foreign Key Enforcement:** All `fact_complaints` records resolve to valid surrogate keys in `dim_agency`, `dim_complaint_type`, `dim_location`, and `dim_calendar`.
- **Row-Level Security (RLS):** Enabled across all public schema tables (`dim_*`, `fact_*`, `quarantine_*`).
- **Read-Only App Role:** Dedicated `readonly_app` PostgreSQL role provisioned with `SELECT`-only privileges.

---

## 5. Verification Commands
```powershell
# Verify live Supabase table counts
.\.venv\Scripts\python scripts/check_live_counts.py
```
