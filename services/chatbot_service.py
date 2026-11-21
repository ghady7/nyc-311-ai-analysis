"""
AI Copilot & Text-to-SQL Analytics Service for NYC 311.
Powered by Gemini 2.5 Flash, AST/table-whitelisting guardrails,
and automated schema grounding.
"""

import os
import re
import time
from typing import Dict, Any, List, Optional
import pandas as pd
import requests
from dotenv import load_dotenv

from src.chatbot.guardrail import (
    sanitize_and_guard_query,
    SecurityViolationError,
    enforce_limit_clause
)
from db.connection import execute_query

load_dotenv()

STAR_SCHEMA_CONTEXT = """
You are a PostgreSQL 17 Analytics Engineer assisting business users with NYC 311 Service Requests data.
Generate ONLY valid, optimized, read-only SELECT queries.
Output ONLY the raw SQL enclosed in ```sql ... ``` code block. Do NOT include any conversational preamble or explanations.

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
   - latitude (NUMERIC)
   - longitude (NUMERIC)
   - ingested_at (TIMESTAMP)

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
4. Provide a reasonable LIMIT (e.g. LIMIT 10 or LIMIT 20) for rankings, top lists, or feeds.
"""

STARTER_QUESTIONS = [
    "What are the top 5 complaint types across NYC?",
    "Which agency has the highest complaint volume and what is their average resolution time?",
    "Compare complaint volume and closure rate across all 5 boroughs",
    "How many complaints were quarantined and what were the rejection reasons?"
]


def generate_sql_query(user_question: str, api_key: Optional[str] = None) -> str:
    """Generate SQL from natural language prompt using Gemini 2.5 Flash."""
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY is not configured. Please set it in .env or provide it in the UI.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": STAR_SCHEMA_CONTEXT},
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

    raw_text = candidates[0]["content"]["parts"][0]["text"]
    return raw_text


def execute_guarded_sql(sql_query: str, max_limit: int = 500) -> Dict[str, Any]:
    """
    Apply AST guardrail and limit ceiling, then execute against PostgreSQL.
    """
    # 1. Sanitize & Enforce AST Guardrail with caller's max_limit ceiling (up to 500)
    guarded_sql = sanitize_and_guard_query(sql_query, max_limit=max_limit)

    # 2. Execute via db.connection
    res = execute_query(guarded_sql, timeout=30)
    rows = res["rows"]
    cols = res["columns"]
    row_count = res["row_count"]
    elapsed_ms = res["execution_time_ms"]

    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=cols)

    return {
        "success": True,
        "guarded_sql": guarded_sql,
        "columns": cols,
        "rows": rows,
        "row_count": row_count,
        "execution_time_ms": elapsed_ms,
        "df": df,
        "error": None
    }


def ask_copilot(user_question: str, api_key: Optional[str] = None, max_limit: int = 500) -> Dict[str, Any]:
    """
    End-to-end pipeline:
    User Question -> Gemini 2.5 Flash -> AST Guardrail -> Supabase Execution -> Structured Result
    """
    start_time = time.time()
    try:
        raw_sql = generate_sql_query(user_question, api_key=api_key)
        exec_res = execute_guarded_sql(raw_sql, max_limit=max_limit)

        row_count = exec_res["row_count"]
        elapsed_ms = exec_res["execution_time_ms"]
        total_time_ms = round((time.time() - start_time) * 1000, 2)

        summary = f"Retrieved **{row_count:,} record(s)** from warehouse in **{elapsed_ms} ms** (total query time {total_time_ms} ms)."

        return {
            "success": True,
            "user_question": user_question,
            "raw_sql": raw_sql,
            "guarded_sql": exec_res["guarded_sql"],
            "columns": exec_res["columns"],
            "rows": exec_res["rows"],
            "row_count": row_count,
            "execution_time_ms": elapsed_ms,
            "df": exec_res["df"],
            "summary": summary,
            "error": None
        }
    except SecurityViolationError as sec_err:
        return {
            "success": False,
            "user_question": user_question,
            "raw_sql": None,
            "guarded_sql": None,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "execution_time_ms": 0.0,
            "df": pd.DataFrame(),
            "summary": f"🛡️ **Security Guardrail Blocked Query**: {sec_err}",
            "error": str(sec_err)
        }
    except Exception as e:
        return {
            "success": False,
            "user_question": user_question,
            "raw_sql": None,
            "guarded_sql": None,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "execution_time_ms": 0.0,
            "df": pd.DataFrame(),
            "summary": f"⚠️ **Execution Error**: {e}",
            "error": str(e)
        }
