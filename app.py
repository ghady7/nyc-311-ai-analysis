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
    page_title="NYC 311 Municipal Operations Center & AI Copilot",
    page_icon="🗽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Executive Enterprise Theme & Typography (Dark Slate Theme)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* Global Typography & Canvas */
    html, body, [class*="css"], .stApp {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
        background-color: #0B0F19 !important;
        color: #F8FAFC !important;
    }

    /* Clean Streamlit Header & Clutter Removal */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 0rem !important;
    }

    /* Container Spacing */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2.5rem !important;
        max-width: 1480px !important;
    }

    /* Bordered Container Card Styling */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: #111827 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 18px -2px rgba(0, 0, 0, 0.35) !important;
    }

    /* Native Metric Cards Styling */
    [data-testid="stMetric"] {
        background: #111827 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        padding: 16px 20px !important;
        box-shadow: 0 4px 18px -2px rgba(0, 0, 0, 0.35) !important;
        transition: border-color 0.15s ease, transform 0.15s ease !important;
    }

    [data-testid="stMetric"]:hover {
        border-color: rgba(99, 102, 241, 0.4) !important;
        transform: translateY(-2px) !important;
    }

    [data-testid="stMetricLabel"] p {
        font-size: 0.72rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
        color: #94A3B8 !important;
        margin: 0 !important;
    }

    [data-testid="stMetricValue"] div {
        font-size: 1.85rem !important;
        font-weight: 800 !important;
        color: #FFFFFF !important;
        letter-spacing: -0.02em !important;
        font-variant-numeric: tabular-nums !important;
    }

    [data-testid="stMetricDelta"] {
        font-size: 0.76rem !important;
        font-weight: 600 !important;
    }

    /* Plotly Chart Card Styling */
    [data-testid="stPlotlyChart"] {
        background: #111827 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        padding: 14px 16px 8px 16px !important;
        box-shadow: 0 4px 18px -2px rgba(0, 0, 0, 0.35) !important;
    }

    /* Streamlit Tabs Navigation */
    .stTabs [data-baseweb="tab-list"] {
        background: #111827 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 10px !important;
        padding: 4px !important;
        gap: 6px !important;
        margin-bottom: 20px !important;
    }

    .stTabs [data-baseweb="tab"] {
        font-weight: 700 !important;
        font-size: 0.88rem !important;
        padding: 8px 18px !important;
        border-radius: 8px !important;
        color: #94A3B8 !important;
        border: none !important;
        background: transparent !important;
    }

    .stTabs [aria-selected="true"] {
        color: #FFFFFF !important;
        background: #1E293B !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3) !important;
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #111827 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }

    /* Buttons */
    .stButton > button {
        background-color: #1E293B !important;
        color: #F8FAFC !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.15s ease !important;
    }

    .stButton > button:hover {
        background-color: #334155 !important;
        border-color: #6366F1 !important;
        color: #FFFFFF !important;
        box-shadow: 0 0 10px rgba(99, 102, 241, 0.3) !important;
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
        col_btn, _ = st.columns([1, 4])
        with col_btn:
            if st.button("🔄 Retry Connection", help="Clear cache and re-query database"):
                clear_dashboard_cache()
                st.rerun()
        st.stop()

    # Format Last Synced Timestamp
    last_synced_raw = freshness.get("last_synced_at")
    if last_synced_raw:
        try:
            clean_ts = str(last_synced_raw).replace("Z", "+00:00")
            dt_synced = datetime.datetime.fromisoformat(clean_ts)
            formatted_synced = dt_synced.strftime("%b %d, %Y %H:%M UTC")
        except Exception:
            formatted_synced = str(last_synced_raw)[:19]
    else:
        formatted_synced = "Live Ingest"

    total_records = int(freshness.get("total_fact_records") or 0)
    pass_rate = float(freshness.get("data_quality_pass_rate") if freshness.get("data_quality_pass_rate") is not None else 100.0)

    # 2. Top Executive Header & Telemetry Deck
    with st.container(border=True):
        head_left, head_right = st.columns([3, 2])
        with head_left:
            st.caption("THE CITY OF NEW YORK · EXECUTIVE OPERATIONS CENTER")
            st.subheader("NYC 311 Operations & Analytics Platform")
            st.caption(
                "Continuous real-time monitoring of civic requests, agency SLA resolution performance, and natural language analytics."
            )
        with head_right:
            t1, t2 = st.columns(2)
            with t1:
                st.caption("WAREHOUSE STATE")
                st.markdown("**Live Ingest**")
                st.caption(f"Synced: {formatted_synced}")
            with t2:
                st.caption("ACTIVE RETENTION")
                st.markdown(f"**{total_records:,}** records")
                st.caption(f"Quality: {pass_rate:.1f}%")

    # 3. Sidebar Refresh Control
    with st.sidebar:
        if st.button("🔄 Sync / Invalidate Cache", use_container_width=True, help="Force refresh latest data from Supabase"):
            clear_dashboard_cache()
            st.rerun()
        st.divider()

    filters = render_sidebar_filters(filter_options)

    # 4. Main Navigation Tabs
    tab_dashboard, tab_copilot = st.tabs([
        "Executive Analytics",
        "AI Analyst Copilot"
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

        # Row 1: Volume Trend & Operational Channel Distribution
        col_trend, col_ops = st.columns([3, 2])
        with col_trend:
            render_volume_trend_chart(trend_df)
        with col_ops:
            render_operational_channels_chart(
                channel_data["channels"],
                channel_data["weekday_vs_weekend"]
            )

        # Row 2: Top Complaint Types & Agency Performance Matrix
        col_types, col_matrix = st.columns([1, 1])
        with col_types:
            render_top_complaints_chart(top_df)
        with col_matrix:
            render_agency_performance_matrix(agency_df)

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
