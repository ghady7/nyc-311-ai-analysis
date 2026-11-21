"""
NYC 311 Rolling Data Retention & Storage Telemetry Engine.
Enforces 30-day rolling data retention on Supabase PostgreSQL to permanently keep
database storage within the 500 MB free tier limit (~160-250 MB footprint).

Dual Connection Architecture:
1. Direct connection (psycopg2 / DATABASE_URL): Executes native DELETE and VACUUM ANALYZE
   under autocommit=True for immediate physical dead tuple reclamation.
2. HTTPS PostgREST / RPC fallback: Executes REST DELETE with service role privileges and
   gathers storage telemetry via authenticated RPC when direct connections are unavailable.
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
import requests
from dotenv import load_dotenv

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from db.connection import execute_query

logger = logging.getLogger("etl.retention")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Configuration defaults
DEFAULT_RETENTION_DAYS = int(os.getenv("RETENTION_DAYS") or "30")
STORAGE_WARN_THRESHOLD_MB = int(os.getenv("STORAGE_WARN_THRESHOLD_MB") or "400")
SUPABASE_FREE_TIER_LIMIT_MB = 500
FREE_TIER_LIMIT_BYTES = SUPABASE_FREE_TIER_LIMIT_MB * 1024 * 1024

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")


def get_supabase_credentials() -> tuple:
    """Dynamically retrieve Supabase URL and Key from environment."""
    url = (os.getenv("SUPABASE_URL") or SUPABASE_URL or "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or SUPABASE_KEY or ""
    return url, key


def get_direct_connection():
    """
    Attempt to establish a direct psycopg2 connection to PostgreSQL.
    Tries DATABASE_URL first, then discrete credentials.
    Returns connection object or None.
    """
    db_url = os.getenv("DATABASE_URL") or DATABASE_URL
    if db_url:
        try:
            import psycopg2
            conn = psycopg2.connect(db_url, connect_timeout=10)
            return conn
        except Exception as exc:
            logger.debug("Direct connection via DATABASE_URL failed: %s", exc)

    host = os.getenv("SUPABASE_DB_HOST")
    user = os.getenv("SUPABASE_DB_USER")
    pw = os.getenv("SUPABASE_DB_PASSWORD")
    if host and user and pw:
        try:
            import psycopg2
            port = int(os.getenv("SUPABASE_DB_PORT", "5432"))
            dbname = os.getenv("SUPABASE_DB_NAME", "postgres")
            conn = psycopg2.connect(
                host=host, port=port, dbname=dbname, user=user, password=pw, connect_timeout=5
            )
            return conn
        except Exception as exc:
            logger.debug("Direct connection via discrete credentials failed: %s", exc)

    return None


def calculate_retention_cutoff(retention_days: int) -> datetime:
    """Calculate the UTC cutoff timestamp for retention."""
    return datetime.now(timezone.utc) - timedelta(days=retention_days)


def parse_content_range_count(content_range: Optional[str]) -> int:
    """
    Extract exact row count from HTTP Content-Range header.
    Format examples: '*/0', '*/150', '0-149/150'.
    """
    if not content_range:
        return 0
    try:
        if "/" in content_range:
            total_part = content_range.split("/")[1].strip()
            if total_part.isdigit():
                return int(total_part)
    except Exception:
        pass
    return 0


def get_storage_telemetry() -> Dict[str, Any]:
    """
    Query database storage consumption, quota utilization, and table row counts.
    Returns telemetry metrics dictionary.
    """
    sql = """
    SELECT 
        pg_database_size(current_database()) AS db_bytes,
        pg_size_pretty(pg_database_size(current_database())) AS db_size_pretty,
        ROUND((pg_database_size(current_database())::numeric / (500 * 1024 * 1024)::numeric) * 100.0, 2) AS pct_of_500mb_quota,
        (SELECT COUNT(*) FROM public.fact_complaints) AS total_facts,
        (SELECT COUNT(*) FROM public.quarantine_complaints) AS total_quarantine;
    """
    res = execute_query(sql)
    if res.get("success") and res.get("rows"):
        row = res["rows"][0]
        db_bytes = int(row.get("db_bytes", 0))
        pct = float(row.get("pct_of_500mb_quota", 0.0))
        db_pretty = str(row.get("db_size_pretty", "Unknown"))
        total_facts = int(row.get("total_facts", 0))
        total_quarantine = int(row.get("total_quarantine", 0))

        warn_bytes = STORAGE_WARN_THRESHOLD_MB * 1024 * 1024
        warn_pct = (STORAGE_WARN_THRESHOLD_MB / SUPABASE_FREE_TIER_LIMIT_MB) * 100.0
        is_warning = db_bytes >= warn_bytes or pct >= warn_pct

        return {
            "db_bytes": db_bytes,
            "db_size_pretty": db_pretty,
            "pct_of_500mb_quota": pct,
            "total_facts": total_facts,
            "total_quarantine": total_quarantine,
            "is_warning": is_warning,
            "free_tier_quota_mb": SUPABASE_FREE_TIER_LIMIT_MB,
            "warning_threshold_mb": STORAGE_WARN_THRESHOLD_MB
        }
    raise RuntimeError("Failed to retrieve storage telemetry from database.")


def count_expired_records(retention_days: int) -> Dict[str, int]:
    """
    Query count of candidate records older than retention window without modifying data.
    """
    retention_days = int(retention_days)
    if retention_days < 1:
        raise ValueError(f"retention_days must be at least 1, got {retention_days}")

    sql = f"""
    SELECT 
        (SELECT COUNT(*) FROM public.fact_complaints WHERE created_timestamp < (CURRENT_TIMESTAMP - INTERVAL '{retention_days} days')) AS expired_facts,
        (SELECT COUNT(*) FROM public.quarantine_complaints WHERE quarantined_at < (CURRENT_TIMESTAMP - INTERVAL '{retention_days} days')) AS expired_quarantine;
    """
    res = execute_query(sql)
    if res.get("success") and res.get("rows"):
        row = res["rows"][0]
        return {
            "expired_facts": int(row.get("expired_facts", 0)),
            "expired_quarantine": int(row.get("expired_quarantine", 0))
        }
    return {"expired_facts": 0, "expired_quarantine": 0}


def prune_expired_facts(retention_days: int, dry_run: bool = False) -> int:
    """
    Delete rows from public.fact_complaints older than retention_days.
    Returns number of pruned records.
    """
    retention_days = int(retention_days)
    if retention_days < 1:
        raise ValueError(f"retention_days must be at least 1, got {retention_days}")

    if dry_run:
        candidates = count_expired_records(retention_days)["expired_facts"]
        logger.info("[DRY RUN] Fact records eligible for pruning: %d", candidates)
        return 0

    # 1. Attempt direct connection deletion
    conn = get_direct_connection()
    if conn:
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM public.fact_complaints WHERE created_timestamp < (CURRENT_TIMESTAMP - INTERVAL '{retention_days} days');"
                )
                deleted = cur.rowcount
                logger.info("Deleted %d expired fact records via direct SQL.", deleted)
                return deleted
        except Exception as exc:
            logger.warning("Direct SQL deletion on fact_complaints failed, falling back to PostgREST: %s", exc)
        finally:
            conn.close()

    # 2. PostgREST REST DELETE fallback
    url, key = get_supabase_credentials()
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY must be configured for PostgREST deletion.")

    cutoff = calculate_retention_cutoff(retention_days)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S")
    delete_url = f"{url}/rest/v1/fact_complaints?created_timestamp=lt.{cutoff_str}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Prefer": "count=exact"
    }

    res = requests.delete(delete_url, headers=headers, timeout=120)
    res.raise_for_status()
    deleted = parse_content_range_count(res.headers.get("content-range"))
    logger.info("Deleted %d expired fact records via PostgREST DELETE.", deleted)
    return deleted


def prune_expired_quarantine(retention_days: int, dry_run: bool = False) -> int:
    """
    Delete rows from public.quarantine_complaints older than retention_days.
    Returns number of pruned records.
    """
    retention_days = int(retention_days)
    if retention_days < 1:
        raise ValueError(f"retention_days must be at least 1, got {retention_days}")

    if dry_run:
        candidates = count_expired_records(retention_days)["expired_quarantine"]
        logger.info("[DRY RUN] Quarantine records eligible for pruning: %d", candidates)
        return 0

    # 1. Attempt direct connection deletion
    conn = get_direct_connection()
    if conn:
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM public.quarantine_complaints WHERE quarantined_at < (CURRENT_TIMESTAMP - INTERVAL '{retention_days} days');"
                )
                deleted = cur.rowcount
                logger.info("Deleted %d expired quarantine records via direct SQL.", deleted)
                return deleted
        except Exception as exc:
            logger.warning("Direct SQL deletion on quarantine_complaints failed, falling back to PostgREST: %s", exc)
        finally:
            conn.close()

    # 2. PostgREST REST DELETE fallback
    url, key = get_supabase_credentials()
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY must be configured for PostgREST deletion.")

    cutoff = calculate_retention_cutoff(retention_days)
    cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    delete_url = f"{url}/rest/v1/quarantine_complaints?quarantined_at=lt.{cutoff_iso}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Prefer": "count=exact"
    }

    res = requests.delete(delete_url, headers=headers, timeout=120)
    res.raise_for_status()
    deleted = parse_content_range_count(res.headers.get("content-range"))
    logger.info("Deleted %d expired quarantine records via PostgREST DELETE.", deleted)
    return deleted


def execute_vacuum(tables: Optional[List[str]] = None) -> bool:
    """
    Execute VACUUM ANALYZE with autocommit=True to reclaim physical tuple space
    and refresh query planner statistics.
    Returns True if successfully executed, False otherwise.
    """
    target_tables = tables or ["fact_complaints", "quarantine_complaints"]

    # 1. Attempt via direct psycopg2 connection
    conn = get_direct_connection()
    if conn:
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                for tbl in target_tables:
                    cur.execute(f"VACUUM ANALYZE public.{tbl};")
                    logger.info("Successfully executed VACUUM ANALYZE on public.%s", tbl)
            return True
        except Exception as exc:
            logger.warning("VACUUM ANALYZE execution via psycopg2 encountered an error: %s", exc)
        finally:
            conn.close()

    # 2. Attempt via SQLAlchemy autocommit engine if DATABASE_URL is configured
    try:
        from db.connection import get_sqlalchemy_engine
        from sqlalchemy import text
        engine = get_sqlalchemy_engine()
        if engine:
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as sa_conn:
                for tbl in target_tables:
                    sa_conn.execute(text(f"VACUUM ANALYZE public.{tbl};"))
                    logger.info("Successfully executed VACUUM ANALYZE on public.%s via SQLAlchemy autocommit", tbl)
            return True
    except Exception as exc:
        logger.debug("SQLAlchemy autocommit VACUUM ANALYZE failed or unavailable: %s", exc)

    logger.info(
        "Direct PostgreSQL connection unavailable for VACUUM ANALYZE; "
        "Supabase PostgreSQL autovacuum daemon manages physical dead tuple reclamation."
    )
    return False


def enforce_rolling_retention(
    retention_days: int = DEFAULT_RETENTION_DAYS,
    dry_run: bool = False,
    min_ingested_rows: int = 1
) -> Dict[str, Any]:
    """
    Master rolling retention cleanup routine.
    Safety Guardrails:
    1. Circuit Breaker: Aborts immediately if min_ingested_rows < 1.
    2. Dimension Table Preservation: Leaves dim_* tables 100% untouched.
    3. Storage Quota Monitoring: Logs warning if database exceeds 400 MB (80%).
    """
    print("\n" + "=" * 70, flush=True)
    print("NYC 311 ROLLING DATA RETENTION & STORAGE ENGINE", flush=True)
    print(f"Retention Window:       {retention_days} Days", flush=True)
    print(f"Execution Mode:         {'DRY RUN (No deletions)' if dry_run else 'LIVE EXECUTION'}", flush=True)
    print(f"Safety Gate Minimum:    {min_ingested_rows:,} Ingested Row(s)", flush=True)
    print("=" * 70, flush=True)

    # 1. Ingestion Failure Circuit Breaker
    if min_ingested_rows < 1:
        msg = (
            f"[CIRCUIT BREAKER] Retention cleanup aborted: min_ingested_rows is {min_ingested_rows} (< 1). "
            "Ingestion may have failed or yielded 0 records. Preserving existing warehouse data."
        )
        logger.error(msg)
        print(f"\n{msg}\n" + "=" * 70 + "\n", flush=True)
        return {
            "status": "aborted",
            "reason": "circuit_breaker_triggered",
            "min_ingested_rows": min_ingested_rows,
            "deleted_facts": 0,
            "deleted_quarantine": 0,
            "dry_run": dry_run
        }

    # 2. Retention Window Safety Guardrail (Prevent accidental total warehouse wipe)
    try:
        retention_days = int(retention_days)
    except (TypeError, ValueError):
        retention_days = -1

    if retention_days < 1:
        msg = (
            f"[CIRCUIT BREAKER] Retention cleanup aborted: retention_days is {retention_days} (< 1). "
            "A retention window of 0 or negative days would prune all existing warehouse data! Aborting."
        )
        logger.error(msg)
        print(f"\n{msg}\n" + "=" * 70 + "\n", flush=True)
        return {
            "status": "aborted",
            "reason": "invalid_retention_days",
            "retention_days": retention_days,
            "min_ingested_rows": min_ingested_rows,
            "deleted_facts": 0,
            "deleted_quarantine": 0,
            "dry_run": dry_run
        }

    # 2. Pre-Execution Telemetry
    pre_telemetry = get_storage_telemetry()
    cutoff_time = calculate_retention_cutoff(retention_days)
    candidate_counts = count_expired_records(retention_days)

    print(f"\n[Pre-Cleanup Status]", flush=True)
    print(f"  Cutoff Timestamp (UTC):   {cutoff_time.strftime('%Y-%m-%d %H:%M:%S UTC')}", flush=True)
    print(f"  Total Fact Complaints:    {pre_telemetry['total_facts']:,}", flush=True)
    print(f"  Total Quarantine Rows:    {pre_telemetry['total_quarantine']:,}", flush=True)
    print(f"  Current Database Storage: {pre_telemetry['db_size_pretty']} ({pre_telemetry['pct_of_500mb_quota']:.2f}% of 500 MB quota)", flush=True)
    print(f"  Expired Fact Candidates:  {candidate_counts['expired_facts']:,}", flush=True)
    print(f"  Expired Quarantine Cands: {candidate_counts['expired_quarantine']:,}", flush=True)

    # 3. Dry-Run Bypass
    if dry_run:
        print("\n[DRY RUN SUMMARY] No rows deleted. Database untouched.", flush=True)
        print("=" * 70 + "\n", flush=True)
        return {
            "status": "dry_run_completed",
            "retention_days": retention_days,
            "cutoff_timestamp": cutoff_time.isoformat(),
            "candidate_facts_to_delete": candidate_counts["expired_facts"],
            "candidate_quarantine_to_delete": candidate_counts["expired_quarantine"],
            "deleted_facts": 0,
            "deleted_quarantine": 0,
            "vacuum_executed": False,
            "telemetry": pre_telemetry
        }

    # 4. Live Row Pruning
    print("\nExecuting live record pruning...", flush=True)
    deleted_facts = prune_expired_facts(retention_days=retention_days, dry_run=False)
    deleted_quarantine = prune_expired_quarantine(retention_days=retention_days, dry_run=False)

    # 5. Dead Tuple Space Reclamation
    print("Executing dead tuple reclamation...", flush=True)
    vacuum_ok = execute_vacuum(["fact_complaints", "quarantine_complaints"])

    # 6. Post-Execution Telemetry
    post_telemetry = get_storage_telemetry()

    print("\n" + "=" * 70, flush=True)
    print("NYC 311 30-DAY ROLLING RETENTION & STORAGE TELEMETRY REPORT", flush=True)
    print("=" * 70, flush=True)
    print(f"Retention Window:         {retention_days} days (Cutoff: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S UTC')})", flush=True)
    print(f"Execution Mode:           LIVE (Dry Run: False)", flush=True)
    print(f"Deleted Fact Rows:        {deleted_facts:,}", flush=True)
    print(f"Deleted Quarantine Rows:  {deleted_quarantine:,}", flush=True)
    print(f"Remaining Fact Rows:      {post_telemetry['total_facts']:,}", flush=True)
    print(f"Remaining Quarantine:     {post_telemetry['total_quarantine']:,}", flush=True)
    print(f"Database Storage Size:    {post_telemetry['db_size_pretty']} / {SUPABASE_FREE_TIER_LIMIT_MB} MB ({post_telemetry['pct_of_500mb_quota']:.2f}% of quota)", flush=True)
    threshold_status = "WARNING (> 80% / 400 MB)" if post_telemetry["is_warning"] else "HEALTHY (< 80% / 400 MB)"
    print(f"Storage Threshold Status: {threshold_status}", flush=True)
    tuple_status = "VACUUM ANALYZE completed" if vacuum_ok else "Queued for Supabase autovacuum daemon"
    print(f"Tuple Space Reclaimed:    {tuple_status}", flush=True)
    print("=" * 70, flush=True)

    if post_telemetry["is_warning"]:
        logger.warning(
            "Database storage reached %s (%.2f%% of 500 MB quota), exceeding %d MB safety threshold!",
            post_telemetry["db_size_pretty"],
            post_telemetry["pct_of_500mb_quota"],
            STORAGE_WARN_THRESHOLD_MB
        )

    return {
        "status": "success",
        "retention_days": retention_days,
        "cutoff_timestamp": cutoff_time.isoformat(),
        "deleted_facts": deleted_facts,
        "deleted_quarantine": deleted_quarantine,
        "remaining_facts": post_telemetry["total_facts"],
        "remaining_quarantine": post_telemetry["total_quarantine"],
        "vacuum_executed": vacuum_ok,
        "telemetry": post_telemetry
    }


def main():
    parser = argparse.ArgumentParser(
        description="NYC 311 Rolling Data Retention & Storage Telemetry Engine"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help=f"Retention window in days (default: {DEFAULT_RETENTION_DAYS} from RETENTION_DAYS env var)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate retention execution and report candidate rows without deleting"
    )
    parser.add_argument(
        "--min-rows",
        type=int,
        default=1,
        help="Minimum required ingested rows for safety circuit breaker (default: 1)"
    )

    args = parser.parse_args()
    enforce_rolling_retention(
        retention_days=args.days,
        dry_run=args.dry_run,
        min_ingested_rows=args.min_rows
    )


if __name__ == "__main__":
    main()
