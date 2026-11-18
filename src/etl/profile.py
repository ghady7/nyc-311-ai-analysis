"""
NYC 311 Service Requests Gate 1 Data Health Profiler
Executes read-only DuckDB profiling queries on raw extraction artifacts.
Zero mutation, zero file writes outside read-only analysis.
"""

import os
import glob
import duckdb


def get_latest_raw_file() -> str:
    """Find the most recent raw compressed JSON file in data/raw/."""
    raw_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw"))
    pattern = os.path.join(raw_dir, "raw_311_*.json.gz")
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"No raw files found matching {pattern}")
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def profile_gate1(raw_file_path: str = None):
    """Run full Gate 1 anomaly audit using DuckDB in-memory engine."""
    if not raw_file_path:
        raw_file_path = get_latest_raw_file()
        
    normalized_path = raw_file_path.replace("\\", "/")
    print("=" * 70)
    print("GATE 1 READ-ONLY DATA HEALTH AUDIT (DUCKDB)")
    print(f"Target Artifact: {normalized_path}")
    print("=" * 70 + "\n")

    con = duckdb.connect(database=":memory:")

    # 1. Volume & Schema
    total_rows = con.execute(f"SELECT COUNT(*) FROM read_ndjson('{normalized_path}');").fetchone()[0]
    schema_rows = con.execute(f"DESCRIBE SELECT * FROM read_ndjson('{normalized_path}');").fetchall()
    print(f"Total Rows:    {total_rows:,}")
    print(f"Total Columns: {len(schema_rows):,}\n")

    # 2. PK Uniqueness
    pk_sql = f"""
    SELECT 
        COUNT(*) AS total_rows,
        COUNT(DISTINCT unique_key) AS distinct_keys,
        COUNT(*) - COUNT(DISTINCT unique_key) AS duplicate_key_count,
        COUNT(CASE WHEN unique_key IS NULL OR TRIM(unique_key) = '' THEN 1 END) AS null_empty_keys
    FROM read_ndjson('{normalized_path}');
    """
    print("--- 2. PRIMARY KEY UNIQUENESS ---")
    print(con.execute(pk_sql).df().to_markdown(index=False))
    print()

    # 3. Date Boundaries
    date_sql = f"""
    SELECT 
        MIN(TRY_CAST(created_date AS TIMESTAMP)) AS min_created_date,
        MAX(TRY_CAST(created_date AS TIMESTAMP)) AS max_created_date,
        MIN(TRY_CAST(closed_date AS TIMESTAMP)) AS min_closed_date,
        MAX(TRY_CAST(closed_date AS TIMESTAMP)) AS max_closed_date,
        COUNT(CASE WHEN TRY_CAST(created_date AS TIMESTAMP) IS NULL THEN 1 END) AS unparseable_created_dates,
        COUNT(CASE WHEN TRY_CAST(created_date AS TIMESTAMP) > CURRENT_TIMESTAMP THEN 1 END) AS future_created_dates,
        COUNT(CASE WHEN TRY_CAST(closed_date AS TIMESTAMP) < TRY_CAST(created_date AS TIMESTAMP) THEN 1 END) AS chronology_violations
    FROM read_ndjson('{normalized_path}');
    """
    print("--- 3. DATE BOUNDARIES & CHRONOLOGY ---")
    print(con.execute(date_sql).df().to_markdown(index=False))
    print()

    # 4. Quarantine Candidates Summary
    q_sql = f"""
    SELECT 
        COUNT(*) AS total_quarantine_records,
        COUNT(CASE WHEN TRY_CAST(closed_date AS TIMESTAMP) < TRY_CAST(created_date AS TIMESTAMP) THEN 1 END) AS chronology_violations,
        COUNT(CASE WHEN borough IS NULL OR TRIM(borough) IN ('', 'Unspecified') THEN 1 END) AS unassigned_boroughs,
        COUNT(CASE WHEN incident_zip IS NOT NULL AND (TRY_CAST(TRIM(incident_zip) AS INTEGER) < 10001 OR TRY_CAST(TRIM(incident_zip) AS INTEGER) > 11697) THEN 1 END) AS non_nyc_zips
    FROM read_ndjson('{normalized_path}')
    WHERE (TRY_CAST(closed_date AS TIMESTAMP) < TRY_CAST(created_date AS TIMESTAMP))
       OR (borough IS NULL OR TRIM(borough) IN ('', 'Unspecified'))
       OR (incident_zip IS NOT NULL AND (TRY_CAST(TRIM(incident_zip) AS INTEGER) < 10001 OR TRY_CAST(TRIM(incident_zip) AS INTEGER) > 11697));
    """
    print("--- 4. QUARANTINE CANDIDATE SUMMARY ---")
    print(con.execute(q_sql).df().to_markdown(index=False))
    print()


if __name__ == "__main__":
    profile_gate1()
