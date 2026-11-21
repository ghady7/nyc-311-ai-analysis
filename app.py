"""
NYC 311 Executive Analytics & AI Copilot System
Unified Streamlit Application combining dynamic PostgreSQL in-database analytics
and Gemini 2.5 Flash Text-to-SQL AI copilot with strict read-only AST guardrails.
Production-ready for Render web service deployment.
"""

import os
import sys
import datetime
import streamlit as st
from dotenv import load_dotenv

# Ensure root workspace is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from db.connection import check_connection
from services.dashboard_service import (
    get_freshness,
    get_filter_options,
    get_kpis,
    get_volume_trend_data,
    get_top_complaints_data,
    get_agency_performance_data,
    get_geographic_data,
    get_channel_metrics_data,
    clear_dashboard_cache
)
from components.filters import render_sidebar_filters
from components.kpi_cards import render_executive_kpis
from components.charts import (
    render_volume_trend_chart,
    render_top_complaints_chart,
    render_agency_performance_matrix,
    render_geographic_charts,
    render_operational_channels_chart
)
from components.chat_interface import render_copilot_chat

load_dotenv()

# Page Configuration
st.set_page_config(
    page_title="NYC 311 Executive Analytics & AI Copilot",
    page_icon="🗽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Executive Dashboard CSS
st.markdown("""
<style>
    /* Metric styling */
    [data-testid="stMetric"] {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 12px 16px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        font-weight: 600;
        color: #4A5568;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.6rem;
        font-weight: 700;
        color: #1A202C;
    }

    /* Badges */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background-color: #EDF2F7;
        color: #2D3748;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid #CBD5E0;
    }
    .status-badge-green {
        background-color: #DEF7EC;
        color: #03543F;
        border-color: #84E1BC;
    }
    .status-badge-blue {
        background-color: #EBF5FF;
        color: #1E429F;
        border-color: #A4CAFE;
    }

    /* Tab headers */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        font-size: 0.95rem;
        padding: 8px 16px;
        border-radius: 6px 6px 0 0;
    }
</style>
""", unsafe_allow_html=True)


# Lightweight Health Check Handler for Render & Monitoring
def handle_health_check():
    """Respond to health check requests if /healthz query param is present."""
    params = st.query_params
    if "healthz" in params or "health" in params:
        health = check_connection()
        if health["connected"]:
            st.json({"status": "healthy", "service": "nyc-311-analytics", "database": "connected", "latency_ms": health["latency_ms"]})
        else:
            st.json({"status": "unhealthy", "service": "nyc-311-analytics", "database": "disconnected", "error": health["error"]})
        st.stop()

handle_health_check()


def main():
    # 1. Fetch Freshness & Filter Options from PostgreSQL
    try:
        freshness = get_freshness()
        filter_options = get_filter_options()
    except Exception as init_err:
        st.error(f"⚠️ Unable to connect to Supabase PostgreSQL: {init_err}")
        st.info("Please verify SUPABASE_URL and SUPABASE_KEY in environment variables.")
        st.stop()

    # Format Last Synced Timestamp
    last_synced_raw = freshness.get("last_synced_at")
    if last_synced_raw:
        try:
            # Parse ISO timestamp and format cleanly
            clean_ts = str(last_synced_raw).replace("Z", "+00:00")
            dt_synced = datetime.datetime.fromisoformat(clean_ts)
            formatted_synced = dt_synced.strftime("%b %d, %Y %H:%M UTC")
        except Exception:
            formatted_synced = str(last_synced_raw)[:19]
    else:
        formatted_synced = "Live Ingest"

    total_records = int(freshness.get("total_fact_records") or 0)
    pass_rate = float(freshness.get("data_quality_pass_rate") if freshness.get("data_quality_pass_rate") is not None else 100.0)

    # 2. Top Header & Synchronization Bar
    head_col1, head_col2 = st.columns([3, 2])
    with head_col1:
        st.title("🗽 NYC 311 Executive Analytics & AI Copilot")
        st.caption("Live municipal service requests, response times, and automated natural language analytics.")

    with head_col2:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        b_col1, b_col2, b_col3 = st.columns([1.8, 1.2, 1.0])
        with b_col1:
            st.markdown(
                f"<div class='status-badge status-badge-blue' title='Timestamp of last automated ETL run'>🔄 Last Synced: {formatted_synced}</div>",
                unsafe_allow_html=True
            )
        with b_col2:
            st.markdown(
                f"<div class='status-badge status-badge-green' title='Clean records / (Clean + Quarantined)'>🛡️ {pass_rate:.1f}% Pass</div>",
                unsafe_allow_html=True
            )
        with b_col3:
            if st.button("🔄 Refresh", help="Invalidate cache and query latest PostgreSQL data"):
                clear_dashboard_cache()
                st.rerun()

    # 3. Sidebar Filters & Environment Information
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/b/ba/Flag_of_New_York_City.svg", width=65)
        st.markdown("### System Architecture")
        st.markdown("🟢 **Warehouse**: Supabase PostgreSQL 17")
        st.markdown(f"📦 **Fact Complaints**: {total_records:,} rows")
        st.markdown("🔒 **Security**: AST Read-Only Guardrail Active")
        st.divider()

    filters = render_sidebar_filters(filter_options)

    # 4. Main Navigation Tabs
    tab_dashboard, tab_copilot = st.tabs([
        "📊 Executive KPI Dashboard",
        "💬 AI Data Analyst Copilot"
    ])

    # ---------------- TAB 1: EXECUTIVE DASHBOARD ----------------
    with tab_dashboard:
        # Load Aggregated Data (Direct from PostgreSQL with TTL cache)
        with st.spinner("Calculating executive aggregations in PostgreSQL..."):
            kpis = get_kpis(filters)
            trend_df = get_volume_trend_data(filters)
            top_df = get_top_complaints_data(filters, limit=12)
            agency_df = get_agency_performance_data(filters)
            geo_data = get_geographic_data(filters)
            channel_data = get_channel_metrics_data(filters)

        # Top Executive KPI Cards Row
        render_executive_kpis(kpis)

        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

        # Row 1: Volume Trend & Operational Channel Distribution
        col_trend, col_ops = st.columns([3, 2])
        with col_trend:
            render_volume_trend_chart(trend_df)
        with col_ops:
            render_operational_channels_chart(
                channel_data["channels"],
                channel_data["weekday_vs_weekend"]
            )

        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

        # Row 2: Top Complaint Types & Agency Performance Matrix
        col_types, col_matrix = st.columns([1, 1])
        with col_types:
            render_top_complaints_chart(top_df)
        with col_matrix:
            render_agency_performance_matrix(agency_df)

        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

        # Row 3: Geographic Breakdown (Boroughs, Zip codes, and Density Map)
        render_geographic_charts(
            geo_data["boroughs"],
            geo_data["top_zips"],
            geo_data["clusters"]
        )

    # ---------------- TAB 2: AI DATA ANALYST COPILOT ----------------
    with tab_copilot:
        render_copilot_chat()


if __name__ == "__main__":
    main()
