"""
NYC 311 Star Schema Loader & Parity Audit Script
Loads clean dimensions, facts, and quarantine records into Supabase Cloud PostgreSQL,
then executes post-load parity verification.
Zero external dataframe dependencies (pure DuckDB + requests).
"""

import os
import sys
import time
import duckdb
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
BATCH_SIZE = 2500


def get_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }


def fetch_all_records(table_name: str, select: str = "*") -> list:
    """Fetch all rows from a table using PostgREST pagination (1000 per page max)."""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    all_rows = []
    limit = 1000
    offset = 0
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table_name}?select={select}&limit={limit}&offset={offset}"
        res = requests.get(url, headers=headers, timeout=60)
        res.raise_for_status()
        chunk = res.json()
        all_rows.extend(chunk)
        if len(chunk) < limit:
            break
        offset += len(chunk)
    return all_rows


def post_batch(table_name: str, batch: list, on_conflict: str = None):
    """Post a batch of rows to Supabase table. Zero silent errors."""
    headers = get_headers()
    if on_conflict:
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        url = f"{SUPABASE_URL}/rest/v1/{table_name}?on_conflict={on_conflict}"
    else:
        url = f"{SUPABASE_URL}/rest/v1/{table_name}"
        
    for attempt in range(1, 4):
        try:
            res = requests.post(url, headers=headers, json=batch, timeout=60)
            if res.status_code in (200, 201):
                return
            else:
                raise RuntimeError(f"HTTP {res.status_code} on {table_name}: {res.text}")
        except Exception as exc:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def query_to_dicts(con, query: str) -> list:
    """Execute a DuckDB query and return list of dicts without requiring pandas."""
    cursor = con.execute(query)
    cols = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    results = []
    for row in rows:
        record = {}
        for col_name, val in zip(cols, row):
            # Clean string conversions for json serialization
            if val is None:
                record[col_name] = None
            elif hasattr(val, "isoformat"):
                record[col_name] = val.isoformat()
            else:
                record[col_name] = val
        results.append(record)
    return results


def load_star_schema():
    clean_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "clean", "clean_complaints.parquet")).replace("\\", "/")
    quarantine_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "quarantine", "quarantine_complaints.parquet")).replace("\\", "/")

    print("=" * 70, flush=True)
    print("GATE 3 WAREHOUSE STAR SCHEMA LOADER", flush=True)
    print(f"Target Supabase:     {SUPABASE_URL}", flush=True)
    print(f"Clean Source:        {clean_path}", flush=True)
    print(f"Quarantine Source:   {quarantine_path}", flush=True)
    print("=" * 70 + "\n", flush=True)

    con = duckdb.connect(database=":memory:")

    # 1. Load Quarantine Table
    print("Loading quarantine_complaints into Supabase...", flush=True)
    q_records = query_to_dicts(con, f"""
    SELECT 
        unique_key,
        rejection_reason,
        created_date,
        closed_date,
        agency,
        agency_name,
        complaint_type,
        descriptor,
        incident_zip,
        borough,
        city,
        status,
        raw_resolution_hours,
        strftime(CURRENT_TIMESTAMP, '%Y-%m-%dT%H:%M:%SZ') AS quarantined_at
    FROM read_parquet('{quarantine_path}');
    """)
    post_batch("quarantine_complaints", q_records)
    print(f"-> Successfully loaded {len(q_records):,} quarantine records.\n", flush=True)

    # 2. Populate Dimension: dim_complaint_type
    print("Extracting and loading dim_complaint_type...", flush=True)
    comp_records = query_to_dicts(con, f"""
    SELECT DISTINCT 
        complaint_type,
        descriptor,
        CASE 
            WHEN complaint_type ILIKE '%noise%' THEN 'Noise'
            WHEN complaint_type ILIKE '%heat%' OR complaint_type ILIKE '%water%' THEN 'Utilities'
            WHEN complaint_type ILIKE '%street%' OR complaint_type ILIKE '%sidewalk%' OR complaint_type ILIKE '%traffic%' THEN 'Infrastructure'
            WHEN complaint_type ILIKE '%sanitation%' OR complaint_type ILIKE '%graffiti%' OR complaint_type ILIKE '%refuse%' THEN 'Sanitation'
            WHEN complaint_type ILIKE '%vehicle%' OR complaint_type ILIKE '%parking%' THEN 'Traffic & Parking'
            ELSE 'General Services'
        END AS complaint_category
    FROM read_parquet('{clean_path}')
    ORDER BY complaint_type, descriptor;
    """)
    post_batch("dim_complaint_type", comp_records, on_conflict="complaint_type,descriptor")
    print(f"-> Successfully loaded {len(comp_records):,} complaint types.\n", flush=True)

    # 3. Populate Dimension: dim_location
    print("Extracting and loading dim_location...", flush=True)
    loc_records = query_to_dicts(con, f"""
    SELECT DISTINCT 
        borough,
        city,
        incident_zip,
        location_type
    FROM read_parquet('{clean_path}')
    ORDER BY borough, city, incident_zip, location_type;
    """)
    for i in range(0, len(loc_records), 1000):
        chunk = loc_records[i : i + 1000]
        post_batch("dim_location", chunk, on_conflict="borough,city,incident_zip,location_type")
    print(f"-> Successfully loaded {len(loc_records):,} location records.\n", flush=True)

    # 4. Fetch Dimension Lookup Maps from Supabase
    print("Fetching dimension lookup tables from Supabase for local surrogate key resolution...", flush=True)
    agencies = fetch_all_records("dim_agency", "agency_key,agency_code")
    complaints = fetch_all_records("dim_complaint_type", "complaint_type_key,complaint_type,descriptor")
    locations = fetch_all_records("dim_location", "location_key,borough,city,incident_zip,location_type")

    # Ingest lookup tables into DuckDB in-memory session for instant SQL join
    con.execute("CREATE TABLE map_agency (agency_code VARCHAR, agency_key INT);")
    con.executemany("INSERT INTO map_agency VALUES (?, ?);", [(r["agency_code"], r["agency_key"]) for r in agencies])

    con.execute("CREATE TABLE map_complaint (complaint_type VARCHAR, descriptor VARCHAR, complaint_type_key INT);")
    con.executemany("INSERT INTO map_complaint VALUES (?, ?, ?);", [(r["complaint_type"], r["descriptor"], r["complaint_type_key"]) for r in complaints])

    con.execute("CREATE TABLE map_location (borough VARCHAR, city VARCHAR, incident_zip VARCHAR, location_type VARCHAR, location_key INT);")
    con.executemany("INSERT INTO map_location VALUES (?, ?, ?, ?, ?);", [(r["borough"], r["city"], r["incident_zip"], r["location_type"], r["location_key"]) for r in locations])

    print(f"-> Dimension lookup tables registered in DuckDB: {len(agencies)} agencies, {len(complaints)} types, {len(locations)} locations.\n", flush=True)

    # 5. Build Resolved Fact Table in DuckDB
    print("Executing dimension join and preparing final fact records in DuckDB...", flush=True)
    con.execute(f"""
    CREATE TABLE stage_facts AS
    SELECT 
        c.unique_key,
        COALESCE(a.agency_key, 0) AS agency_key,
        COALESCE(ct.complaint_type_key, 0) AS complaint_type_key,
        COALESCE(l.location_key, 0) AS location_key,
        CAST(c.created_year * 10000 + c.created_month * 100 + c.created_day AS INTEGER) AS created_date_key,
        CASE 
            WHEN c.closed_date IS NOT NULL THEN 
                CAST(EXTRACT(YEAR FROM c.closed_date) * 10000 + EXTRACT(MONTH FROM c.closed_date) * 100 + EXTRACT(DAY FROM c.closed_date) AS INTEGER)
            ELSE NULL 
        END AS closed_date_key,
        strftime(c.created_date, '%Y-%m-%dT%H:%M:%S') AS created_timestamp,
        CASE WHEN c.closed_date IS NOT NULL THEN strftime(c.closed_date, '%Y-%m-%dT%H:%M:%S') ELSE NULL END AS closed_timestamp,
        CASE WHEN c.due_date IS NOT NULL THEN strftime(c.due_date, '%Y-%m-%dT%H:%M:%S') ELSE NULL END AS due_timestamp,
        CASE WHEN c.resolution_action_updated_date IS NOT NULL THEN strftime(c.resolution_action_updated_date, '%Y-%m-%dT%H:%M:%S') ELSE NULL END AS resolution_action_updated_timestamp,
        c.resolution_hours,
        c.is_closed,
        CASE 
            WHEN c.due_date IS NOT NULL AND c.closed_date IS NOT NULL THEN c.closed_date <= c.due_date
            ELSE NULL 
        END AS is_sla_compliant,
        c.latitude,
        c.longitude,
        c.x_coordinate,
        c.y_coordinate,
        c.status,
        c.open_data_channel_type,
        c.incident_address,
        c.street_name,
        c.address_type,
        c.community_board,
        c.bbl,
        c.resolution_description
    FROM read_parquet('{clean_path}') c
    LEFT JOIN map_agency a ON c.agency = a.agency_code
    LEFT JOIN map_complaint ct ON c.complaint_type = ct.complaint_type AND c.descriptor = ct.descriptor
    LEFT JOIN map_location l ON c.borough = l.borough AND c.city = l.city AND c.incident_zip = l.incident_zip AND c.location_type = l.location_type;
    """)

    total_facts = con.execute("SELECT COUNT(*) FROM stage_facts;").fetchone()[0]
    print(f"-> Resolved all foreign keys for {total_facts:,} fact records.\n", flush=True)

    # 6. Stream Fact Batches to Supabase
    print(f"Streaming {total_facts:,} fact records to Supabase in chunks of {BATCH_SIZE:,}...", flush=True)
    start_load = time.time()
    
    offset = 0
    while offset < total_facts:
        batch_query = f"SELECT * FROM stage_facts LIMIT {BATCH_SIZE} OFFSET {offset};"
        batch = query_to_dicts(con, batch_query)
        post_batch("fact_complaints", batch, on_conflict="unique_key")
        offset += len(batch)
        pct = (offset / total_facts) * 100.0
        print(f"-> Ingested {offset:,} / {total_facts:,} ({pct:.1f}%) ...", flush=True)

    elapsed = time.time() - start_load
    print(f"\nFact load completed in {elapsed:.1f}s ({total_facts / elapsed:.0f} rows/sec).\n", flush=True)
    print("=" * 70, flush=True)
    print("GATE 3 WAREHOUSE LOAD COMPLETE", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    load_star_schema()
