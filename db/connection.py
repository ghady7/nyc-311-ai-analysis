"""
Database Connection & Execution Engine for NYC 311 Analytics.
Supports primary authenticated HTTPS PostgREST RPC and optional
direct SQLAlchemy/psycopg2 pooled connection fallback.
"""

import os
import time
from typing import Dict, Any, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
DEFAULT_TIMEOUT = int(os.getenv("DB_TIMEOUT", "30"))

# SQLAlchemy engine lazy singleton for direct DB connections
_sql_engine = None


def get_supabase_credentials() -> tuple:
    """Retrieve Supabase URL and API Key dynamically from environment."""
    url = (os.getenv("SUPABASE_URL") or SUPABASE_URL or "").rstrip("/")
    key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or SUPABASE_KEY or ""
    return url, key


def get_sqlalchemy_engine():
    """Lazily initialize and return SQLAlchemy connection pool if DATABASE_URL is configured."""
    global _sql_engine
    db_url = os.getenv("DATABASE_URL") or DATABASE_URL
    if _sql_engine is None and db_url:
        from sqlalchemy import create_engine
        from sqlalchemy.pool import QueuePool
        _sql_engine = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={"connect_timeout": 10}
        )
    return _sql_engine


def execute_via_https_rpc(sql_query: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """
    Execute read-only SQL query via Supabase PostgREST RPC endpoint.
    This guarantees 100% IPv4/IPv6 compatibility on cloud hosts (e.g. Render)
    and executes inside the hardened execute_readonly_query security definer.
    """
    url, key = get_supabase_credentials()
    if not url:
        raise ValueError("SUPABASE_URL environment variable is not configured.")
    if not key:
        raise ValueError("SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY environment variable is not configured.")

    # Strip trailing whitespace and semicolons for RPC execution compatibility
    clean_sql = sql_query.strip().rstrip(";").strip()

    rpc_url = f"{url}/rest/v1/rpc/execute_readonly_query"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    payload = {"query_text": clean_sql}

    start_time = time.time()
    try:
        response = requests.post(rpc_url, headers=headers, json=payload, timeout=timeout)
    except requests.exceptions.Timeout:
        raise TimeoutError(f"Database query exceeded timeout of {timeout} seconds.")
    except requests.exceptions.RequestException as req_err:
        raise ConnectionError(f"Network error connecting to Supabase: {req_err}")

    elapsed_ms = round((time.time() - start_time) * 1000, 2)

    if response.status_code == 200:
        data = response.json()
        if isinstance(data, list):
            cols = list(data[0].keys()) if len(data) > 0 else []
            return {
                "success": True,
                "columns": cols,
                "rows": data,
                "row_count": len(data),
                "execution_time_ms": elapsed_ms
            }
        elif isinstance(data, dict):
            return {
                "success": True,
                "columns": list(data.keys()),
                "rows": [data],
                "row_count": 1,
                "execution_time_ms": elapsed_ms
            }
        else:
            return {
                "success": True,
                "columns": ["result"],
                "rows": [{"result": data}],
                "row_count": 1,
                "execution_time_ms": elapsed_ms
            }
    else:
        err_msg = response.text
        try:
            err_json = response.json()
            if isinstance(err_json, dict) and "message" in err_json:
                err_msg = err_json["message"]
        except Exception:
            pass
        raise RuntimeError(f"Database execution error ({response.status_code}): {err_msg}")


def execute_via_sqlalchemy(sql_query: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """Execute read-only SQL query via SQLAlchemy direct connection pool."""
    from sqlalchemy import text
    engine = get_sqlalchemy_engine()
    if not engine:
        raise ValueError("DATABASE_URL is not configured for direct database connection.")

    start_time = time.time()
    with engine.connect() as conn:
        # Enforce statement timeout in Postgres session
        conn.execute(text(f"SET statement_timeout = '{timeout * 1000}';"))
        result = conn.execute(text(sql_query))
        cols = list(result.keys()) if result.returns_rows else []
        rows = [dict(zip(cols, row)) for row in result.fetchall()] if result.returns_rows else []

    elapsed_ms = round((time.time() - start_time) * 1000, 2)
    return {
        "success": True,
        "columns": cols,
        "rows": rows,
        "row_count": len(rows),
        "execution_time_ms": elapsed_ms
    }


def execute_query(sql_query: str, timeout: int = DEFAULT_TIMEOUT, prefer_direct: bool = False) -> Dict[str, Any]:
    """
    Execute SQL query using dual-mode routing:
    1. Primary: HTTPS PostgREST RPC (default, resilient across IPv4/IPv6 networks).
    2. Fallback / Direct: SQLAlchemy if prefer_direct=True or if HTTPS is unavailable and DATABASE_URL is set.
    """
    if prefer_direct and DATABASE_URL:
        try:
            return execute_via_sqlalchemy(sql_query, timeout=timeout)
        except Exception as direct_err:
            # Fall back to HTTPS RPC if direct fails
            return execute_via_https_rpc(sql_query, timeout=timeout)
    else:
        try:
            return execute_via_https_rpc(sql_query, timeout=timeout)
        except Exception as rpc_err:
            if DATABASE_URL:
                return execute_via_sqlalchemy(sql_query, timeout=timeout)
            raise rpc_err


def check_connection() -> Dict[str, Any]:
    """Health check routine verifying Supabase PostgreSQL connectivity and latency."""
    start_time = time.time()
    try:
        res = execute_query("SELECT 1 AS health_check", timeout=5)
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "status": "healthy",
            "connected": True,
            "latency_ms": elapsed_ms,
            "error": None
        }
    except Exception as e:
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "status": "unhealthy",
            "connected": False,
            "latency_ms": elapsed_ms,
            "error": str(e)
        }
