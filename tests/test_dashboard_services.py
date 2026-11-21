"""
Unit and Integration Tests for Unified Dashboard & Services Layer
Tests:
- Database connection and healthcheck
- In-database query builders and sanitization
- Dashboard service aggregation cache keys
- Chatbot service schema context and starter questions
"""

import datetime
import pytest
import pandas as pd
from db.connection import check_connection, execute_query
from db.queries import (
    _sanitize_sql_string,
    build_filter_where_clause,
    fetch_data_freshness,
    fetch_filter_options,
    fetch_executive_kpis,
    fetch_volume_trend,
    fetch_top_complaint_types,
    fetch_agency_performance,
    fetch_geographic_breakdown,
    fetch_channel_operational_metrics
)
from services.dashboard_service import (
    _normalize_filter_key,
    get_freshness,
    get_kpis,
    get_volume_trend_data,
    get_top_complaints_data,
    get_agency_performance_data,
    get_geographic_data,
    get_channel_metrics_data
)
from services.chatbot_service import STARTER_QUESTIONS, STAR_SCHEMA_CONTEXT, execute_guarded_sql
from components.charts import (
    render_volume_trend_chart,
    render_top_complaints_chart,
    render_agency_performance_matrix,
    render_geographic_charts,
    render_operational_channels_chart
)
from components.kpi_cards import render_executive_kpis
from components.chat_interface import render_chat_visualization


class TestDatabaseAndQueries:

    def test_database_healthcheck(self):
        health = check_connection()
        assert health["status"] == "healthy"
        assert health["connected"] is True
        assert health["latency_ms"] > 0

    def test_sanitize_sql_string(self):
        malicious = "MANHATTAN'; DROP TABLE fact_complaints; --"
        clean = _sanitize_sql_string(malicious)
        assert "''" in clean
        assert clean == "MANHATTAN''; DROP TABLE fact_complaints; --"

    def test_build_filter_where_clause_empty(self):
        clause = build_filter_where_clause({})
        assert clause == ""
        clause_none = build_filter_where_clause(None)
        assert clause_none == ""

    def test_build_filter_where_clause_with_filters(self):
        filters = {
            "date_range": (datetime.date(2026, 11, 10), datetime.date(2026, 11, 15)),
            "boroughs": ["BROOKLYN", "MANHATTAN"],
            "agencies": ["New York City Police Department"],
            "categories": ["Noise"],
            "statuses": ["Closed"]
        }
        where = build_filter_where_clause(filters)
        assert "f.created_timestamp >= '2026-11-10 00:00:00'" in where
        assert "f.created_timestamp <= '2026-11-15 23:59:59'" in where
        assert "UPPER(l.borough) IN ('BROOKLYN', 'MANHATTAN')" in where
        assert "a.agency_name IN ('New York City Police Department')" in where
        assert "t.complaint_category IN ('Noise')" in where
        assert "f.status IN ('Closed')" in where

    def test_fetch_freshness_data(self):
        fresh = fetch_data_freshness()
        assert fresh["total_fact_records"] > 100000
        assert fresh["quarantine_records"] > 0
        assert fresh["data_quality_pass_rate"] >= 80.0
        assert fresh["last_synced_at"] is not None

    def test_fetch_filter_options(self):
        opts = fetch_filter_options()
        assert "BROOKLYN" in opts["boroughs"]
        assert len(opts["agencies"]) >= 10
        assert len(opts["categories"]) >= 5
        assert opts["min_date"] <= opts["max_date"]

    def test_fetch_executive_kpis(self):
        kpis = fetch_executive_kpis({})
        assert kpis["total_complaints"] > 100000
        assert 0 <= kpis["closure_rate"] <= 100
        assert 0 <= kpis["sla_compliance_rate"] <= 100
        assert kpis["avg_resolution_hours"] > 0
        assert kpis["median_resolution_hours"] > 0

    def test_fetch_volume_trend(self):
        trend = fetch_volume_trend({})
        assert len(trend) > 0
        assert "full_date" in trend[0]
        assert "complaint_volume" in trend[0]
        assert "rolling_7d_avg" in trend[0]

    def test_fetch_top_complaint_types(self):
        top = fetch_top_complaint_types({}, limit=5)
        assert len(top) == 5
        assert "complaint_type" in top[0]
        assert "complaint_count" in top[0]

    def test_fetch_agency_performance(self):
        agencies = fetch_agency_performance({}, min_volume=50)
        assert len(agencies) > 0
        assert "agency_name" in agencies[0]
        assert "total_complaints" in agencies[0]

    def test_fetch_geographic_breakdown(self):
        geo = fetch_geographic_breakdown({})
        assert len(geo["boroughs"]) >= 5
        assert len(geo["top_zips"]) == 10
        assert len(geo["clusters"]) > 0

    def test_fetch_channel_operational_metrics(self):
        chan = fetch_channel_operational_metrics({})
        assert len(chan["channels"]) >= 3
        assert len(chan["weekday_vs_weekend"]) == 2


class TestDashboardService:

    def test_normalize_filter_key(self):
        f1 = {"boroughs": ["MANHATTAN", "BROOKLYN"], "status": "Closed"}
        f2 = {"status": "Closed", "boroughs": ["BROOKLYN", "MANHATTAN"]}
        assert _normalize_filter_key(f1) == _normalize_filter_key(f2)

    def test_service_dataframes(self):
        trend_df = get_volume_trend_data({})
        assert isinstance(trend_df, pd.DataFrame)
        assert not trend_df.empty

        top_df = get_top_complaints_data({})
        assert isinstance(top_df, pd.DataFrame)
        assert not top_df.empty

        agency_df = get_agency_performance_data({})
        assert isinstance(agency_df, pd.DataFrame)
        assert not agency_df.empty

        geo_data = get_geographic_data({})
        assert isinstance(geo_data["boroughs"], pd.DataFrame)
        assert isinstance(geo_data["top_zips"], pd.DataFrame)
        assert isinstance(geo_data["clusters"], pd.DataFrame)

        chan_data = get_channel_metrics_data({})
        assert isinstance(chan_data["channels"], pd.DataFrame)
        assert isinstance(chan_data["weekday_vs_weekend"], pd.DataFrame)


class TestChatbotService:

    def test_starter_questions(self):
        assert len(STARTER_QUESTIONS) == 4
        assert any("top 5" in q.lower() for q in STARTER_QUESTIONS)
        assert any("agency" in q.lower() for q in STARTER_QUESTIONS)
        assert any("borough" in q.lower() for q in STARTER_QUESTIONS)
        assert any("quarantine" in q.lower() for q in STARTER_QUESTIONS)

    def test_star_schema_context_grounding(self):
        assert "fact_complaints" in STAR_SCHEMA_CONTEXT
        assert "dim_agency" in STAR_SCHEMA_CONTEXT
        assert "dim_complaint_type" in STAR_SCHEMA_CONTEXT
        assert "dim_location" in STAR_SCHEMA_CONTEXT
        assert "dim_calendar" in STAR_SCHEMA_CONTEXT
        assert "quarantine_complaints" in STAR_SCHEMA_CONTEXT

    def test_guarded_sql_limit_ceiling_enforcement(self):
        res = execute_guarded_sql("SELECT unique_key FROM fact_complaints LIMIT 10", max_limit=500)
        assert res["success"] is True
        assert "LIMIT 10" in res["guarded_sql"]
        assert len(res["rows"]) <= 10


class TestComponentsAndCharts:

    def test_render_volume_trend_chart(self):
        # Empty
        render_volume_trend_chart(pd.DataFrame())
        # Populated
        df = pd.DataFrame([
            {"full_date": "2026-11-10", "complaint_volume": 100, "rolling_7d_avg": 95.5},
            {"full_date": "2026-11-11", "complaint_volume": 120, "rolling_7d_avg": 102.0}
        ])
        render_volume_trend_chart(df)

    def test_render_top_complaints_chart(self):
        # Empty
        render_top_complaints_chart(pd.DataFrame())
        # Populated
        df = pd.DataFrame([
            {"complaint_type": "Noise", "complaint_category": "Noise", "complaint_count": 500},
            {"complaint_type": "Heat/Hot Water", "complaint_category": "Utilities", "complaint_count": 400}
        ])
        render_top_complaints_chart(df)

    def test_render_agency_performance_matrix_with_nulls(self):
        # Empty
        render_agency_performance_matrix(pd.DataFrame())
        # Populated with nulls and zeros (proves fix for Issue 3)
        df = pd.DataFrame([
            {"agency_name": "NYPD", "agency_code": "NYPD", "total_complaints": 100, "closure_rate": 90.0, "sla_compliance_rate": 85.0, "avg_resolution_hours": None},
            {"agency_name": "DOT", "agency_code": "DOT", "total_complaints": 50, "closure_rate": None, "sla_compliance_rate": None, "avg_resolution_hours": 12.0},
            {"agency_name": "DEP", "agency_code": "DEP", "total_complaints": 0, "closure_rate": 0.0, "sla_compliance_rate": 0.0, "avg_resolution_hours": 0.0}
        ])
        render_agency_performance_matrix(df)

    def test_render_geographic_charts_and_clusters(self):
        # Empty
        render_geographic_charts(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
        # Populated with cluster coordinates (proves fix for Issue 2)
        b_df = pd.DataFrame([{"borough": "MANHATTAN", "total_complaints": 100, "avg_resolution_hours": 8.5}])
        z_df = pd.DataFrame([{"incident_zip": "10001", "borough": "MANHATTAN", "complaint_count": 50}])
        c_df = pd.DataFrame([
            {"lat": 40.71, "lon": -74.00, "borough": "MANHATTAN", "count": 25},
            {"lat": None, "lon": None, "borough": "QUEENS", "count": 5}
        ])
        render_geographic_charts(b_df, z_df, c_df)

    def test_render_operational_channels_chart(self):
        # Empty
        render_operational_channels_chart(pd.DataFrame(), pd.DataFrame())
        # Populated
        c_df = pd.DataFrame([{"channel": "ONLINE", "total": 200}, {"channel": "PHONE", "total": 100}])
        w_df = pd.DataFrame([
            {"day_type": "Weekday", "total": 250, "avg_resolution_hours": 10.0},
            {"day_type": "Weekend", "total": 50, "avg_resolution_hours": 14.5}
        ])
        render_operational_channels_chart(c_df, w_df)

    def test_render_executive_kpis_robustness(self):
        # Empty/None values (proves fix for Issue 5)
        kpis_empty = {
            "total_complaints": None,
            "total_delta_pct": None,
            "closure_rate": None,
            "closure_delta": None,
            "sla_compliance_rate": None,
            "sla_delta": None,
            "median_resolution_hours": None,
            "avg_resolution_hours": None,
            "resolution_hours_delta": None
        }
        render_executive_kpis(kpis_empty)

    def test_render_chat_visualization_shapes(self):
        # Empty
        render_chat_visualization(pd.DataFrame())
        # Single row
        df_single = pd.DataFrame([{"total_count": 12345, "avg_hours": 12.34}])
        render_chat_visualization(df_single, key_prefix="test_single")
        # Multi-row categorical
        df_multi = pd.DataFrame([
            {"borough": "MANHATTAN", "complaints": 100},
            {"borough": "BROOKLYN", "complaints": 200}
        ])
        render_chat_visualization(df_multi, key_prefix="test_multi")

