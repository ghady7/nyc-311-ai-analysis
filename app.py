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

# Custom Executive Enterprise Theme & Typography
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    html, body, [class*="css"], .stApp {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        color: #0F172A;
        background-color: #F8FAFC;
    }

    /* Streamlit layout spacing cleanup */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 3rem !important;
        max-width: 1440px !important;
    }

    /* Header Container */
    .executive-header {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        padding: 20px 24px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
    }

    .header-left {
        flex: 1;
        min-width: 320px;
    }

    .header-pretitle {
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.1em;
        color: #4F46E5;
        text-transform: uppercase;
        margin-bottom: 4px;
    }

    .header-title {
        font-size: 1.75rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        color: #0F172A;
        margin: 0;
        line-height: 1.2;
    }

    .header-caption {
        font-size: 0.85rem;
        color: #64748B;
        margin-top: 4px;
        margin-bottom: 0;
    }

    /* Live Telemetry Capsule */
    .telemetry-capsule {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
    }

    .status-capsule-item {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        background: #F1F5F9;
        color: #334155;
        border: 1px solid #E2E8F0;
    }

    .capsule-live {
        background: #ECFDF5;
        color: #065F46;
        border-color: #A7F3D0;
    }

    .capsule-blue {
        background: #EEF2FF;
        color: #3730A3;
        border-color: #C7D2FE;
    }

    /* Pulsing Beacon */
    .live-beacon {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #10B981;
        box-shadow: 0 0 0 rgba(16, 185, 129, 0.4);
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }

    /* KPI Grid & Cards */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
        gap: 16px;
        margin-bottom: 20px;
    }

    .kpi-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px -1px rgba(0, 0, 0, 0.02);
        transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }

    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 16px -2px rgba(0, 0, 0, 0.06);
        border-color: #CBD5E1;
    }

    .kpi-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
    }

    .kpi-tag {
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        color: #64748B;
        text-transform: uppercase;
    }

    .kpi-icon-badge {
        width: 28px;
        height: 28px;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.85rem;
    }

    .badge-indigo { background: rgba(79, 70, 229, 0.1); color: #4F46E5; }
    .badge-emerald { background: rgba(16, 185, 129, 0.1); color: #10B981; }
    .badge-sky { background: rgba(14, 165, 233, 0.1); color: #0EA5E9; }
    .badge-amber { background: rgba(245, 158, 11, 0.1); color: #F59E0B; }

    .kpi-body {
        margin-bottom: 10px;
    }

    .kpi-value {
        font-size: 1.85rem;
        font-weight: 800;
        color: #0F172A;
        letter-spacing: -0.02em;
        line-height: 1.2;
    }

    .kpi-unit {
        font-size: 1.05rem;
        font-weight: 600;
        color: #64748B;
    }

    .kpi-progress-track {
        width: 100%;
        height: 5px;
        background: #F1F5F9;
        border-radius: 999px;
        overflow: hidden;
        margin-top: 8px;
    }

    .kpi-progress-fill {
        height: 100%;
        border-radius: 999px;
        transition: width 0.4s ease;
    }

    .kpi-footer {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
    }

    .kpi-pill {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 999px;
    }

    .kpi-pill-success {
        background-color: #ECFDF5;
        color: #065F46;
        border: 1px solid #A7F3D0;
    }

    .kpi-pill-danger {
        background-color: #FEF2F2;
        color: #991B1B;
        border: 1px solid #FECACA;
    }

    .kpi-pill-neutral {
        background-color: #F1F5F9;
        color: #334155;
        border: 1px solid #E2E8F0;
    }

    .kpi-context {
        font-size: 0.76rem;
        color: #64748B;
        font-weight: 500;
    }

    /* Plotly Chart Card Styling */
    [data-testid="stPlotlyChart"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 12px 14px 6px 14px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
    }

    /* Streamlit Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: transparent;
        border-bottom: 2px solid #E2E8F0;
        padding-bottom: 2px;
    }

    .stTabs [data-baseweb="tab"] {
        font-weight: 700;
        font-size: 0.95rem;
        padding: 10px 18px;
        border-radius: 8px 8px 0 0;
        color: #64748B;
    }

    .stTabs [aria-selected="true"] {
        color: #4F46E5 !important;
        border-bottom: 2px solid #4F46E5 !important;
        background-color: rgba(79, 70, 229, 0.04);
    }

    /* Sidebar Telemetry Card */
    .sidebar-telemetry-box {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 16px;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
    }

    .telemetry-title {
        font-size: 0.7rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        color: #4F46E5;
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 10px;
    }

    .telemetry-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background-color: #10B981;
    }

    .telemetry-item {
        display: flex;
        justify-content: space-between;
        font-size: 0.78rem;
        margin-bottom: 6px;
    }

    .telemetry-lbl {
        color: #64748B;
        font-weight: 500;
    }

    .telemetry-val {
        color: #0F172A;
        font-weight: 600;
    }

    .telemetry-storage-track {
        margin-top: 10px;
        padding-top: 8px;
        border-top: 1px solid #F1F5F9;
    }

    .telemetry-storage-label {
        display: flex;
        justify-content: space-between;
        font-size: 0.72rem;
        color: #64748B;
        margin-bottom: 4px;
    }

    .telemetry-storage-pct {
        font-weight: 700;
        color: #0F172A;
    }

    .telemetry-storage-bar {
        width: 100%;
        height: 5px;
        background: #F1F5F9;
        border-radius: 999px;
        overflow: hidden;
    }

    .telemetry-storage-fill {
        height: 100%;
        background: #4F46E5;
        border-radius: 999px;
    }

    .active-filter-pill {
        display: inline-block;
        padding: 3px 8px;
        background: #EEF2FF;
        color: #4F46E5;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 700;
        border: 1px solid #C7D2FE;
    }

    .all-data-pill {
        display: inline-block;
        padding: 3px 8px;
        background: #F1F5F9;
        color: #64748B;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    /* Copilot Hero Banner */
    .copilot-hero-banner {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
    }

    .copilot-badge {
        font-size: 0.7rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        color: #4F46E5;
        margin-bottom: 4px;
    }

    .copilot-title {
        font-size: 1.4rem;
        font-weight: 800;
        color: #0F172A;
        margin-bottom: 6px;
    }

    .copilot-desc {
        font-size: 0.86rem;
        color: #64748B;
        line-height: 1.5;
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
            clean_ts = str(last_synced_raw).replace("Z", "+00:00")
            dt_synced = datetime.datetime.fromisoformat(clean_ts)
            formatted_synced = dt_synced.strftime("%b %d, %Y %H:%M UTC")
        except Exception:
            formatted_synced = str(last_synced_raw)[:19]
    else:
        formatted_synced = "Live Ingest"

    total_records = int(freshness.get("total_fact_records") or 0)
    pass_rate = float(freshness.get("data_quality_pass_rate") if freshness.get("data_quality_pass_rate") is not None else 100.0)

    # 2. Top Executive Header & Telemetry Control Deck
    header_html = f"""
    <div class="executive-header">
        <div class="header-left">
            <div class="header-pretitle">THE CITY OF NEW YORK · EXECUTIVE OPERATIONS CENTER</div>
            <h1 class="header-title">NYC 311 Municipal Analytics & Copilot</h1>
            <p class="header-caption">Continuous real-time monitoring of civic requests, SLA resolution performance, and natural language analytics.</p>
        </div>
        <div class="telemetry-capsule">
            <div class="status-capsule-item capsule-live" title="Automated daily ETL is active">
                <span class="live-beacon"></span> LIVE WAREHOUSE
            </div>
            <div class="status-capsule-item capsule-blue" title="Timestamp of last automated ETL run">
                🔄 Synced: {formatted_synced}
            </div>
            <div class="status-capsule-item" title="Clean records / (Clean + Quarantined)">
                🛡️ {pass_rate:.1f}% Quality
            </div>
            <div class="status-capsule-item" title="Total active fact records">
                📦 {total_records:,} Records
            </div>
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)

    # 3. Sidebar Filters & System Architecture
    with st.sidebar:
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
            <div style="font-size: 1.8rem;">🗽</div>
            <div>
                <div style="font-size: 0.95rem; font-weight: 800; color: #0F172A; line-height: 1.2;">NYC 311 OPS</div>
                <div style="font-size: 0.72rem; color: #64748B; font-weight: 600;">Intelligence Platform</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🔄 Sync / Invalidate Cache", use_container_width=True, help="Force refresh latest data from Supabase"):
            clear_dashboard_cache()
            st.rerun()

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

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        # Row 1: Volume Trend & Operational Channel Distribution
        col_trend, col_ops = st.columns([3, 2])
        with col_trend:
            render_volume_trend_chart(trend_df)
        with col_ops:
            render_operational_channels_chart(
                channel_data["channels"],
                channel_data["weekday_vs_weekend"]
            )

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        # Row 2: Top Complaint Types & Agency Performance Matrix
        col_types, col_matrix = st.columns([1, 1])
        with col_types:
            render_top_complaints_chart(top_df)
        with col_matrix:
            render_agency_performance_matrix(agency_df)

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

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
