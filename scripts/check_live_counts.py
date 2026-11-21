import sys, os
sys.path.insert(0, os.path.abspath("."))
from db.connection import execute_query

for t in ['fact_complaints', 'quarantine_complaints', 'dim_agency', 'dim_complaint_type', 'dim_location', 'dim_calendar']:
    res = execute_query(f"SELECT count(*) as cnt FROM {t}")
    cnt = res['rows'][0]['cnt']
    print(f"{t}: {cnt}")
