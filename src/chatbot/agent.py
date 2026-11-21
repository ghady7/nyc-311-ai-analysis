"""
Gemini 2.5 Flash Text-to-SQL Agent for NYC 311 Analytics
Converts natural language analytical questions into guarded, read-only PostgreSQL queries.
"""

import os
import re
import time
from typing import Dict, Any, List, Optional
import requests
from dotenv import load_dotenv
from src.chatbot.guardrail import sanitize_and_guard_query, SecurityViolationError

load_dotenv()

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

SCHEMA_CONTEXT = """
You are a PostgreSQL 17 Analytics Engineer assisting business users with NYC 311 Service Requests data.
Generate ONLY valid, optimized, read-only SELECT queries. Do NOT explain the query in the main output, output ONLY the SQL inside ```sql ... ``` code block.

TERMINOLOGY & INTENT MAPPING:
- 'problem', 'issue', 'ticket', 'incident', or 'complaint' refers to 311 service requests stored in fact_complaints.
- 'where' refers to location: dim_location.borough, dim_location.incident_zip, or fact_complaints.incident_address.
- 'when' refers to timing: fact_complaints.created_timestamp or dim_calendar.full_date.
- 'recent' or 'latest' refers to ORDER BY fact_complaints.created_timestamp DESC.
- 'most common', 'most frequent', or 'top' refers to COUNT(*) ... GROUP BY ... ORDER BY count DESC.
- ONLY query 'quarantine_complaints' if the user explicitly asks for 'quarantine', 'rejected', 'corrupted', or 'invalid' records.

DATABASE SCHEMA:
1. fact_complaints (Central Fact Table of valid 311 service requests):
   - unique_key (VARCHAR, Primary Key)
   - agency_key (INT, FK -> dim_agency.agency_key)
   - complaint_type_key (INT, FK -> dim_complaint_type.complaint_type_key)
   - location_key (INT, FK -> dim_location.location_key)
   - created_date_key (INT, FK -> dim_calendar.date_key, Format YYYYMMDD)
   - closed_date_key (INT, FK -> dim_calendar.date_key, Format YYYYMMDD, NULL if open)
   - created_timestamp (TIMESTAMP)
   - closed_timestamp (TIMESTAMP, NULL if open)
   - resolution_hours (NUMERIC, calculated closure time in hours, NULL if open)
   - is_closed (BOOLEAN, TRUE if closed)
   - is_sla_compliant (BOOLEAN)
   - status (VARCHAR: 'Closed', 'Open', 'In Progress', 'Assigned', 'Pending')
   - open_data_channel_type (VARCHAR: 'PHONE', 'ONLINE', 'MOBILE', 'UNKNOWN')
   - incident_address (VARCHAR)
   - street_name (VARCHAR)
   - community_board (VARCHAR)
   - resolution_description (TEXT)

2. dim_agency:
   - agency_key (INT, PK)
   - agency_code (VARCHAR, e.g. 'NYPD', 'HPD', 'DSNY', 'DOT', 'DEP', 'DOB')
   - agency_name (VARCHAR, Full title e.g. 'New York City Police Department')

3. dim_complaint_type:
   - complaint_type_key (INT, PK)
   - complaint_type (VARCHAR, e.g. 'Noise - Residential', 'Heat/Hot Water', 'Blocked Driveway')
   - descriptor (VARCHAR, granular reason e.g. 'Loud Music/Party', 'No Heat')
   - complaint_category (VARCHAR: 'Noise', 'Utilities', 'Infrastructure', 'Sanitation', 'Traffic & Parking', 'General Services')

4. dim_location:
   - location_key (INT, PK)
   - borough (VARCHAR: 'BROOKLYN', 'MANHATTAN', 'QUEENS', 'BRONX', 'STATEN ISLAND')
   - city (VARCHAR)
   - incident_zip (VARCHAR: 5-digit postal code)
   - location_type (VARCHAR, e.g. 'Residential Building', 'Street/Sidewalk')

5. dim_calendar:
   - date_key (INT, PK, YYYYMMDD)
   - full_date (DATE)
   - year (SMALLINT), month (SMALLINT), month_name (VARCHAR), day_name (VARCHAR), is_weekend (BOOLEAN)

6. quarantine_complaints (Isolated Data Quality Audit Table for rejected records):
   - CRITICAL RULE: NEVER JOIN quarantine_complaints with fact_complaints or any dim table. It is completely independent.
   - quarantine_id (SERIAL, PK)
   - unique_key (VARCHAR)
   - rejection_reason (VARCHAR: 'CHRONOLOGY_VIOLATION', 'UNASSIGNED_BOROUGH', 'INVALID_OR_OUT_OF_STATE_ZIP')
   - created_date (VARCHAR)
   - closed_date (VARCHAR)
   - agency (VARCHAR)
   - complaint_type (VARCHAR)
   - borough (VARCHAR)
   - raw_resolution_hours (NUMERIC)

QUERY WRITING RULES:
1. Always JOIN fact_complaints with relevant dimensions to return human-readable names (e.g. JOIN dim_complaint_type ON fact_complaints.complaint_type_key = dim_complaint_type.complaint_type_key).
2. For resolution time / SLA metrics, filter for closed tickets: `WHERE fact_complaints.is_closed = TRUE` or `WHERE fact_complaints.resolution_hours IS NOT NULL`.
3. For borough filtering, use UPPER(dim_location.borough) = '...'.
4. Provide a reasonable LIMIT (e.g. LIMIT 10 or LIMIT 20) for rankings, top lists, or recent feeds.
"""


def generate_sql_from_question(user_question: str, api_key: Optional[str] = None) -> str:
    """Generate SQL from natural language prompt using Gemini API."""
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY is not set. Please provide it in sidebar or .env file.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": SCHEMA_CONTEXT},
                    {"text": f"User Analytical Question: {user_question}\nGenerate PostgreSQL SQL Query:"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048,
            "thinkingConfig": {
                "thinkingBudget": 0
            }
        }
    }

    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()

    result = response.json()
    candidates = result.get("candidates", [])
    if not candidates:
        raise RuntimeError("No candidate response generated by Gemini model.")

    text_content = candidates[0]["content"]["parts"][0]["text"]
    return text_content


def execute_guarded_query(sql_query: str) -> Dict[str, Any]:
    """
    Pass raw query through security guardrail, then execute via Supabase read-only role.
    """
    start_time = time.time()

    # 1. Enforce AST & Security Guardrail
    guarded_sql = sanitize_and_guard_query(sql_query)

    # 2. Execute via Supabase REST RPC endpoint
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    rpc_url = f"{SUPABASE_URL}/rest/v1/rpc/execute_readonly_query"

    res = requests.post(rpc_url, headers=headers, json={"query_text": guarded_sql}, timeout=30)
    elapsed_ms = round((time.time() - start_time) * 1000, 2)

    if res.status_code == 200:
        data = res.json()
        if isinstance(data, list) and data:
            cols = list(data[0].keys())
        else:
            cols = []
        return {
            "success": True,
            "guarded_sql": guarded_sql,
            "columns": cols,
            "rows": data if isinstance(data, list) else [],
            "row_count": len(data) if isinstance(data, list) else 0,
            "execution_time_ms": elapsed_ms
        }
    else:
        err_msg = res.text
        try:
            err_json = res.json()
            if isinstance(err_json, dict) and "message" in err_json:
                err_msg = err_json["message"]
        except Exception:
            pass
        raise RuntimeError(f"Database execution error: {err_msg}")


def ask_analytics_agent(user_question: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """End-to-end pipeline: Natural language -> Gemini SQL -> Guardrail -> Execution."""
    raw_sql = generate_sql_from_question(user_question, api_key=api_key)
    guarded_sql = sanitize_and_guard_query(raw_sql)
    return {
        "user_question": user_question,
        "raw_sql": raw_sql,
        "guarded_sql": guarded_sql
    }
