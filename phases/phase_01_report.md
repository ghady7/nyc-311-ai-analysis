# Phase 01 Report: Ingestion & Profiling Audit

## 1. Phase Objective & Status
- **Objective:** Extract rolling 30-day NYC 311 service request records via Socrata Open Data API with pagination, store compressed immutable raw backup, and run read-only DuckDB profiling to audit schema, null rates, cardinality, and boundary conditions.
- **Status:** **COMPLETE & VERIFIED**

---

## 2. Artifacts Created & Modified
| Artifact | Path | Purpose |
| :--- | :--- | :--- |
| **Extraction Script** | `src/etl/extract.py` | Socrata API rolling 30-day pagination extractor. |
| **Profiling Script** | `src/etl/profile.py` | Read-only DuckDB profiling suite. |
| **Raw Backup** | `data/raw/raw_311_20261118_203000.json.gz` | Compressed raw extraction (50,000 records). |

---

## 3. Profiling Health Summary
DuckDB in-memory inspection of `raw_311_20261118_203000.json.gz`:

| Metric | Measured Value | Threshold / Target | Health Status |
| :--- | :--- | :--- | :--- |
| **Total Ingested Records** | 50,000 | >= 30,000 | **PASS** |
| **Unique Candidate PKs (`unique_key`)** | 50,000 | 100% Unique | **PASS** |
| **Agency Cardinality** | 16 distinct agencies | Expected (10-25) | **PASS** |
| **Complaint Types** | 184 distinct types | High cardinality | **PASS** |
| **Missing Boroughs** | 41 records (0.08%) | < 1% | **FLAGGED FOR QUARANTINE** |
| **Malformed ZIP Codes** | 29 records (0.06%) | < 1% | **FLAGGED FOR QUARANTINE** |
| **Date Ordering Inversions** | 0 records (`closed_date < created_date`) | 0 | **PASS** |

---

## 4. Anomalies & Quarantine Rules Established
1. **Malformed ZIP Codes:** Non-numeric or invalid length postal codes routed to quarantine with error code `INVALID_ZIP`.
2. **Missing Boroughs / Locations:** Records missing essential geographic attributes routed with `MISSING_LOCATION`.
3. **Date Inversions:** Enforced validation asserting `created_date <= closed_date` and `created_date <= current_timestamp`.

---

## 5. Verification Commands
```powershell
# Profile raw JSON with DuckDB
.\.venv\Scripts\python src/etl/profile.py --input data/raw/raw_311_20261118_203000.json.gz
```
