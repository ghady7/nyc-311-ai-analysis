"""
In-Database SQL Aggregation Queries for NYC 311 Executive Analytics.
Executes all aggregations, window functions, and percentiles directly inside
Supabase PostgreSQL 17 to prevent loading unaggregated records into application memory.
"""

import datetime
from typing import Dict, Any, List, Optional, Tuple
from db.connection import execute_query


def _sanitize_sql_string(val: str) -> str:
    """Sanitize string literal for SQL clause injection prevention."""
    return str(val).replace("'", "''").strip()


def build_filter_where_clause(filters: Optional[Dict[str, Any]] = None) -> str:
    """
    Compile UI filter dictionary into a parameterized SQL WHERE clause.
    Standard table aliases:
      f: fact_complaints
      l: dim_location
      a: dim_agency
      t: dim_complaint_type
      c: dim_calendar
    """
    if not filters:
        return ""

    conditions: List[str] = []

    # 1. Date Range Filter
    date_range = filters.get("date_range")
    if date_range and len(date_range) == 2:
        start_date, end_date = date_range
        if start_date and end_date:
            s_str = start_date.isoformat() if hasattr(start_date, "isoformat") else str(start_date)
            e_str = end_date.isoformat() if hasattr(end_date, "isoformat") else str(end_date)
            conditions.append(f"f.created_timestamp >= '{_sanitize_sql_string(s_str)} 00:00:00'")
            conditions.append(f"f.created_timestamp <= '{_sanitize_sql_string(e_str)} 23:59:59'")

    # 2. Boroughs Multi-Select Filter
    boroughs = filters.get("boroughs")
    if boroughs and isinstance(boroughs, (list, tuple)):
        clean_boroughs = [f"'{_sanitize_sql_string(b)}'" for b in boroughs if b]
        if clean_boroughs:
            conditions.append(f"UPPER(l.borough) IN ({', '.join(clean_boroughs)})")

    # 3. Agency Multi-Select Filter
    agencies = filters.get("agencies")
    if agencies and isinstance(agencies, (list, tuple)):
        clean_agencies = [f"'{_sanitize_sql_string(a)}'" for a in agencies if a]
        if clean_agencies:
            conditions.append(f"a.agency_name IN ({', '.join(clean_agencies)})")

    # 4. Complaint Category Multi-Select Filter
    categories = filters.get("categories")
    if categories and isinstance(categories, (list, tuple)):
        clean_cats = [f"'{_sanitize_sql_string(c)}'" for c in categories if c]
        if clean_cats:
            conditions.append(f"t.complaint_category IN ({', '.join(clean_cats)})")

    # 5. Status Multi-Select Filter
    statuses = filters.get("statuses")
    if statuses and isinstance(statuses, (list, tuple)):
        clean_statuses = [f"'{_sanitize_sql_string(s)}'" for s in statuses if s]
        if clean_statuses:
            conditions.append(f"f.status IN ({', '.join(clean_statuses)})")

    if not conditions:
        return ""

    return "WHERE " + " AND ".join(conditions)


def fetch_data_freshness() -> Dict[str, Any]:
    """
    Query real-time metadata: last ingested timestamp badge,
    total warehouse records count, date boundaries, and quarantine data pass rate.
    """
    sql = """
    SELECT
        COUNT(*) AS total_fact_records,
        MAX(f.ingested_at) AS last_synced_at,
        MIN(f.created_timestamp) AS min_created_at,
        MAX(f.created_timestamp) AS max_created_at,
        (SELECT COUNT(*) FROM quarantine_complaints) AS quarantine_records
    FROM fact_complaints f
    """
    res = execute_query(sql)
    if not res["rows"]:
        return {
            "total_fact_records": 0,
            "last_synced_at": None,
            "min_created_at": None,
            "max_created_at": None,
            "quarantine_records": 0,
            "data_quality_pass_rate": 100.0
        }

    row = res["rows"][0]
    fact_count = int(row.get("total_fact_records") or 0)
    quarantine_count = int(row.get("quarantine_records") or 0)
    total_pipeline = fact_count + quarantine_count
    pass_rate = round((fact_count / total_pipeline) * 100.0, 2) if total_pipeline > 0 else 100.0

    return {
        "total_fact_records": fact_count,
        "last_synced_at": row.get("last_synced_at"),
        "min_created_at": row.get("min_created_at"),
        "max_created_at": row.get("max_created_at"),
        "quarantine_records": quarantine_count,
        "data_quality_pass_rate": pass_rate
    }


def fetch_filter_options() -> Dict[str, Any]:
    """
    Query distinct options for global sidebar filters directly from dimensions.
    """
    sql_boroughs = "SELECT DISTINCT borough FROM dim_location WHERE borough IS NOT NULL ORDER BY borough;"
    sql_agencies = "SELECT DISTINCT agency_name FROM dim_agency WHERE agency_name IS NOT NULL ORDER BY agency_name;"
    sql_categories = "SELECT DISTINCT complaint_category FROM dim_complaint_type WHERE complaint_category IS NOT NULL ORDER BY complaint_category;"
    sql_statuses = "SELECT DISTINCT status FROM fact_complaints WHERE status IS NOT NULL ORDER BY status;"
    sql_dates = "SELECT MIN(created_timestamp::date) AS min_date, MAX(created_timestamp::date) AS max_date FROM fact_complaints;"

    boroughs_res = execute_query(sql_boroughs)
    agencies_res = execute_query(sql_agencies)
    categories_res = execute_query(sql_categories)
    statuses_res = execute_query(sql_statuses)
    dates_res = execute_query(sql_dates)

    date_row = dates_res["rows"][0] if dates_res["rows"] else {}
    min_date_str = date_row.get("min_date")
    max_date_str = date_row.get("max_date")

    min_date = datetime.date.fromisoformat(min_date_str) if min_date_str else datetime.date.today() - datetime.timedelta(days=30)
    max_date = datetime.date.fromisoformat(max_date_str) if max_date_str else datetime.date.today()

    return {
        "boroughs": [r["borough"] for r in boroughs_res["rows"] if r.get("borough")],
        "agencies": [r["agency_name"] for r in agencies_res["rows"] if r.get("agency_name")],
        "categories": [r["complaint_category"] for r in categories_res["rows"] if r.get("complaint_category")],
        "statuses": [r["status"] for r in statuses_res["rows"] if r.get("status")],
        "min_date": min_date,
        "max_date": max_date
    }


def fetch_executive_kpis(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Calculate executive KPI metrics with period-over-period delta comparisons:
    - Total Complaints (with % volume delta)
    - Closure Rate % (with percentage point delta)
    - SLA Compliance Rate % (with percentage point delta)
    - Median & Mean Resolution Time in Hours (with hours delta)
    """
    where_clause = build_filter_where_clause(filters)

    sql_current = f"""
    SELECT
        COUNT(*) AS total_complaints,
        COUNT(CASE WHEN f.is_closed = true THEN 1 END) AS closed_complaints,
        ROUND(100.0 * COUNT(CASE WHEN f.is_closed = true THEN 1 END) / NULLIF(COUNT(*), 0), 2) AS closure_rate,
        COUNT(CASE WHEN f.is_sla_compliant = true THEN 1 END) AS sla_compliant_complaints,
        ROUND(100.0 * COUNT(CASE WHEN f.is_sla_compliant = true THEN 1 END) / NULLIF(COUNT(CASE WHEN f.is_closed = true THEN 1 END), 0), 2) AS sla_compliance_rate,
        ROUND(AVG(f.resolution_hours)::numeric, 2) AS avg_resolution_hours,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.resolution_hours)::numeric, 2) AS median_resolution_hours
    FROM fact_complaints f
    LEFT JOIN dim_location l ON f.location_key = l.location_key
    LEFT JOIN dim_agency a ON f.agency_key = a.agency_key
    LEFT JOIN dim_complaint_type t ON f.complaint_type_key = t.complaint_type_key
    LEFT JOIN dim_calendar c ON f.created_date_key = c.date_key
    {where_clause};
    """

    res_current = execute_query(sql_current)
    curr = res_current["rows"][0] if res_current["rows"] else {}

    # Determine prior period for comparison
    prior_filters = dict(filters) if filters else {}
    date_range = prior_filters.get("date_range")

    if date_range and len(date_range) == 2 and date_range[0] and date_range[1]:
        start_d, end_d = date_range
        duration_days = max(1, (end_d - start_d).days + 1)
        prior_start = start_d - datetime.timedelta(days=duration_days)
        prior_end = start_d - datetime.timedelta(days=1)
        prior_filters["date_range"] = (prior_start, prior_end)
    else:
        # If no explicit date range, compare last 7 days vs previous 7 days based on data boundary
        freshness = fetch_data_freshness()
        max_d_str = freshness.get("max_created_at")
        if max_d_str:
            max_dt = datetime.datetime.fromisoformat(str(max_d_str)[:10]).date()
            curr_start = max_dt - datetime.timedelta(days=6)
            prior_start = curr_start - datetime.timedelta(days=7)
            prior_end = curr_start - datetime.timedelta(days=1)
            prior_filters["date_range"] = (prior_start, prior_end)

    prior_where = build_filter_where_clause(prior_filters)
    sql_prior = f"""
    SELECT
        COUNT(*) AS total_complaints,
        ROUND(100.0 * COUNT(CASE WHEN f.is_closed = true THEN 1 END) / NULLIF(COUNT(*), 0), 2) AS closure_rate,
        ROUND(100.0 * COUNT(CASE WHEN f.is_sla_compliant = true THEN 1 END) / NULLIF(COUNT(CASE WHEN f.is_closed = true THEN 1 END), 0), 2) AS sla_compliance_rate,
        ROUND(AVG(f.resolution_hours)::numeric, 2) AS avg_resolution_hours,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.resolution_hours)::numeric, 2) AS median_resolution_hours
    FROM fact_complaints f
    LEFT JOIN dim_location l ON f.location_key = l.location_key
    LEFT JOIN dim_agency a ON f.agency_key = a.agency_key
    LEFT JOIN dim_complaint_type t ON f.complaint_type_key = t.complaint_type_key
    LEFT JOIN dim_calendar c ON f.created_date_key = c.date_key
    {prior_where};
    """
    res_prior = execute_query(sql_prior)
    prior = res_prior["rows"][0] if res_prior["rows"] else {}

    # Extract current metrics
    total = int(curr.get("total_complaints") or 0)
    closure_rate = float(curr.get("closure_rate") or 0.0)
    sla_rate = float(curr.get("sla_compliance_rate") or 0.0)
    avg_hours = float(curr.get("avg_resolution_hours") or 0.0)
    median_hours = float(curr.get("median_resolution_hours") or 0.0)

    # Extract prior metrics
    prior_total = int(prior.get("total_complaints") or 0)
    prior_closure = float(prior.get("closure_rate") or 0.0)
    prior_sla = float(prior.get("sla_compliance_rate") or 0.0)
    prior_avg_hours = float(prior.get("avg_resolution_hours") or 0.0)

    # Compute deltas
    total_delta_pct = round(((total - prior_total) / prior_total) * 100.0, 1) if prior_total > 0 else 0.0
    closure_delta = round(closure_rate - prior_closure, 1)
    sla_delta = round(sla_rate - prior_sla, 1)
    hours_delta = round(avg_hours - prior_avg_hours, 1)

    return {
        "total_complaints": total,
        "total_delta_pct": total_delta_pct,
        "closure_rate": closure_rate,
        "closure_delta": closure_delta,
        "sla_compliance_rate": sla_rate,
        "sla_delta": sla_delta,
        "avg_resolution_hours": avg_hours,
        "median_resolution_hours": median_hours,
        "resolution_hours_delta": hours_delta,
        "prior_total_complaints": prior_total
    }


def fetch_volume_trend(filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Query daily complaint volume time series with a 7-day rolling average
    computed in-database via SQL window function.
    """
    where_clause = build_filter_where_clause(filters)

    sql = f"""
    SELECT
        c.full_date,
        COUNT(f.unique_key) AS complaint_volume,
        ROUND(AVG(COUNT(f.unique_key)) OVER (
            ORDER BY c.full_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        )::numeric, 1) AS rolling_7d_avg
    FROM fact_complaints f
    JOIN dim_calendar c ON f.created_date_key = c.date_key
    LEFT JOIN dim_location l ON f.location_key = l.location_key
    LEFT JOIN dim_agency a ON f.agency_key = a.agency_key
    LEFT JOIN dim_complaint_type t ON f.complaint_type_key = t.complaint_type_key
    {where_clause}
    GROUP BY c.full_date
    ORDER BY c.full_date ASC;
    """
    return execute_query(sql)["rows"]


def fetch_top_complaint_types(filters: Optional[Dict[str, Any]] = None, limit: int = 15) -> List[Dict[str, Any]]:
    """
    Query top complaint types and associated categories sorted by descending volume.
    """
    where_clause = build_filter_where_clause(filters)

    sql = f"""
    SELECT
        t.complaint_type,
        t.complaint_category,
        COUNT(*) AS complaint_count
    FROM fact_complaints f
    JOIN dim_complaint_type t ON f.complaint_type_key = t.complaint_type_key
    LEFT JOIN dim_location l ON f.location_key = l.location_key
    LEFT JOIN dim_agency a ON f.agency_key = a.agency_key
    LEFT JOIN dim_calendar c ON f.created_date_key = c.date_key
    {where_clause}
    GROUP BY t.complaint_type, t.complaint_category
    ORDER BY complaint_count DESC
    LIMIT {limit};
    """
    return execute_query(sql)["rows"]


def fetch_agency_performance(filters: Optional[Dict[str, Any]] = None, min_volume: int = 20) -> List[Dict[str, Any]]:
    """
    Query agency performance matrix: Volume vs. SLA Compliance % vs. Avg Resolution Hours.
    """
    where_clause = build_filter_where_clause(filters)

    sql = f"""
    SELECT
        a.agency_name,
        a.agency_code,
        COUNT(*) AS total_complaints,
        ROUND(100.0 * COUNT(CASE WHEN f.is_closed = true THEN 1 END) / NULLIF(COUNT(*), 0), 1) AS closure_rate,
        ROUND(100.0 * COUNT(CASE WHEN f.is_sla_compliant = true THEN 1 END) / NULLIF(COUNT(CASE WHEN f.is_closed = true THEN 1 END), 0), 1) AS sla_compliance_rate,
        ROUND(AVG(f.resolution_hours)::numeric, 1) AS avg_resolution_hours
    FROM fact_complaints f
    JOIN dim_agency a ON f.agency_key = a.agency_key
    LEFT JOIN dim_location l ON f.location_key = l.location_key
    LEFT JOIN dim_complaint_type t ON f.complaint_type_key = t.complaint_type_key
    LEFT JOIN dim_calendar c ON f.created_date_key = c.date_key
    {where_clause}
    GROUP BY a.agency_name, a.agency_code
    HAVING COUNT(*) >= {min_volume}
    ORDER BY total_complaints DESC;
    """
    return execute_query(sql)["rows"]


def fetch_geographic_breakdown(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Query geographic breakdown:
    1. Volume & resolution hours across 5 NYC boroughs
    2. Top 10 incident zip codes
    3. Coordinate cluster density sample (rounded to 2 decimals)
    """
    where_clause = build_filter_where_clause(filters)

    sql_boroughs = f"""
    SELECT
        l.borough,
        COUNT(*) AS total_complaints,
        ROUND(AVG(f.resolution_hours)::numeric, 1) AS avg_resolution_hours,
        ROUND(100.0 * COUNT(CASE WHEN f.is_closed = true THEN 1 END) / NULLIF(COUNT(*), 0), 1) AS closure_rate
    FROM fact_complaints f
    JOIN dim_location l ON f.location_key = l.location_key
    LEFT JOIN dim_agency a ON f.agency_key = a.agency_key
    LEFT JOIN dim_complaint_type t ON f.complaint_type_key = t.complaint_type_key
    LEFT JOIN dim_calendar c ON f.created_date_key = c.date_key
    {where_clause}
    GROUP BY l.borough
    ORDER BY total_complaints DESC;
    """

    and_clause = "AND" if where_clause else "WHERE"
    sql_zips = f"""
    SELECT
        l.incident_zip,
        l.borough,
        COUNT(*) AS complaint_count
    FROM fact_complaints f
    JOIN dim_location l ON f.location_key = l.location_key
    LEFT JOIN dim_agency a ON f.agency_key = a.agency_key
    LEFT JOIN dim_complaint_type t ON f.complaint_type_key = t.complaint_type_key
    LEFT JOIN dim_calendar c ON f.created_date_key = c.date_key
    {where_clause}
    {and_clause} l.incident_zip IS NOT NULL
    GROUP BY l.incident_zip, l.borough
    ORDER BY complaint_count DESC
    LIMIT 10;
    """

    sql_clusters = f"""
    SELECT
        ROUND(f.latitude::numeric, 2) AS lat,
        ROUND(f.longitude::numeric, 2) AS lon,
        l.borough,
        COUNT(*) AS count
    FROM fact_complaints f
    JOIN dim_location l ON f.location_key = l.location_key
    LEFT JOIN dim_agency a ON f.agency_key = a.agency_key
    LEFT JOIN dim_complaint_type t ON f.complaint_type_key = t.complaint_type_key
    LEFT JOIN dim_calendar c ON f.created_date_key = c.date_key
    {where_clause}
    {and_clause} f.latitude IS NOT NULL AND f.longitude IS NOT NULL
    GROUP BY ROUND(f.latitude::numeric, 2), ROUND(f.longitude::numeric, 2), l.borough
    ORDER BY count DESC
    LIMIT 200;
    """

    return {
        "boroughs": execute_query(sql_boroughs)["rows"],
        "top_zips": execute_query(sql_zips)["rows"],
        "clusters": execute_query(sql_clusters)["rows"]
    }


def fetch_channel_operational_metrics(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Query operational channel distribution (Online, Phone, Mobile)
    and Weekday vs Weekend ticket volume and resolution time split.
    """
    where_clause = build_filter_where_clause(filters)

    sql_channels = f"""
    SELECT
        COALESCE(f.open_data_channel_type, 'UNKNOWN') AS channel,
        COUNT(*) AS total
    FROM fact_complaints f
    LEFT JOIN dim_location l ON f.location_key = l.location_key
    LEFT JOIN dim_agency a ON f.agency_key = a.agency_key
    LEFT JOIN dim_complaint_type t ON f.complaint_type_key = t.complaint_type_key
    LEFT JOIN dim_calendar c ON f.created_date_key = c.date_key
    {where_clause}
    GROUP BY COALESCE(f.open_data_channel_type, 'UNKNOWN')
    ORDER BY total DESC;
    """

    sql_dow = f"""
    SELECT
        CASE WHEN c.is_weekend THEN 'Weekend' ELSE 'Weekday' END AS day_type,
        COUNT(*) AS total,
        ROUND(AVG(f.resolution_hours)::numeric, 1) AS avg_resolution_hours
    FROM fact_complaints f
    JOIN dim_calendar c ON f.created_date_key = c.date_key
    LEFT JOIN dim_location l ON f.location_key = l.location_key
    LEFT JOIN dim_agency a ON f.agency_key = a.agency_key
    LEFT JOIN dim_complaint_type t ON f.complaint_type_key = t.complaint_type_key
    {where_clause}
    GROUP BY c.is_weekend
    ORDER BY total DESC;
    """

    channels_rows = execute_query(sql_channels)["rows"]
    total_channel_volume = sum(r["total"] for r in channels_rows)
    for r in channels_rows:
        r["pct"] = round((r["total"] / total_channel_volume) * 100.0, 1) if total_channel_volume > 0 else 0.0

    return {
        "channels": channels_rows,
        "weekday_vs_weekend": execute_query(sql_dow)["rows"]
    }
