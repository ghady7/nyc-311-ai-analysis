import sys, os, time
sys.path.insert(0, os.path.abspath("."))
from src.chatbot.agent import execute_guarded_query

queries = [
    ("Top 5 complaint types", "SELECT c.complaint_type, count(*) as total FROM fact_complaints f JOIN dim_complaint_type c ON f.complaint_type_key = c.complaint_type_key GROUP BY c.complaint_type ORDER BY total DESC LIMIT 5"),
    ("Agency longest avg resolution hours", "SELECT a.agency_name, round(avg(f.resolution_hours), 2) as avg_hours FROM fact_complaints f JOIN dim_agency a ON f.agency_key = a.agency_key WHERE f.is_closed = TRUE GROUP BY a.agency_name ORDER BY avg_hours DESC LIMIT 5"),
    ("Compare complaint volume across 5 boroughs", "SELECT l.borough, count(*) as total FROM fact_complaints f JOIN dim_location l ON f.location_key = l.location_key GROUP BY l.borough ORDER BY total DESC"),
    ("Quarantine complaints breakdown", "SELECT rejection_reason, count(*) as count FROM quarantine_complaints GROUP BY rejection_reason ORDER BY count DESC"),
    ("Avg resolution time for Noise in Manhattan", "SELECT round(avg(f.resolution_hours), 2) as avg_hours FROM fact_complaints f JOIN dim_location l ON f.location_key = l.location_key JOIN dim_complaint_type c ON f.complaint_type_key = c.complaint_type_key WHERE l.borough = 'MANHATTAN' AND c.complaint_type ILIKE '%Noise%' AND f.is_closed = TRUE")
]

for name, sql in queries:
    t0 = time.time()
    try:
        res = execute_guarded_query(sql)
        elapsed = round(time.time() - t0, 2)
        print(f"PASS: '{name}' executed in {elapsed}s | Rows: {res['row_count']}")
    except Exception as e:
        print(f"FAIL: '{name}': {e}")
