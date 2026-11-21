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

# Unified Enterprise Design System (Obsidian Slate Dark Theme)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
        --bg-canvas: #090D16;
        --bg-sidebar: #0D1320;
        --bg-surface: #111827;
        --bg-surface-elevated: #172033;
        --bg-surface-hover: #1E293B;

        --border-subtle: rgba(148, 163, 184, 0.14);
        --border-strong: rgba(148, 163, 184, 0.24);
        --border-accent: rgba(99, 102, 241, 0.52);

        --text-primary: #F8FAFC;
        --text-secondary: #CBD5E1;
        --text-muted: #94A3B8;

        --accent-primary: #6366F1;
        --accent-primary-light: #818CF8;
        --accent-sky: #38BDF8;
        --semantic-positive: #34D399;
        --semantic-warning: #FBBF24;
        --semantic-critical: #F87171;

        --radius-sm: 6px;
        --radius-md: 10px;
        --radius-lg: 14px;

        --shadow-card: 0 1px 2px rgba(0, 0, 0, 0.35), 0 8px 24px -6px rgba(0, 0, 0, 0.45);
        --shadow-card-hover: 0 4px 12px rgba(0, 0, 0, 0.45), 0 12px 28px -6px rgba(0, 0, 0, 0.55);
        --focus-ring: 0 0 0 2px #090D16, 0 0 0 4px #6366F1;

        --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
    }

    /* Global Canvas & Typography */
    html, body, [class*="css"], .stApp {
        font-family: var(--font-sans) !important;
        background-color: var(--bg-canvas) !important;
        color: var(--text-primary) !important;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    code, pre, [data-testid="stCodeBlock"] {
        font-family: var(--font-mono) !important;
        font-variant-numeric: tabular-nums !important;
    }

    /* Chrome Cleanup Without Blocking Sidebar Toggle */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    [data-testid="stDecoration"] { display: none !important; }
    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    /* Main Container Rhythm */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 3rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 1520px !important;
    }

    /* Prevent Flex / Grid Overflow on Charts & Tables */
    [data-testid="column"],
    [data-testid="stColumn"],
    [data-testid="stHorizontalBlock"] > div {
        min-width: 0 !important;
    }

    /* Typography Hierarchy */
    h1, h2, h3, h4 {
        color: var(--text-primary) !important;
        letter-spacing: -0.02em !important;
        font-weight: 700 !important;
    }

    h3 {
        font-size: 1.35rem !important;
        line-height: 1.25 !important;
        margin-bottom: 0.25rem !important;
    }

    h4 {
        font-size: 0.96rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.01em !important;
        margin-top: 0.75rem !important;
        margin-bottom: 0.15rem !important;
    }

    [data-testid="stCaptionContainer"] {
        color: var(--text-muted) !important;
        font-size: 0.78rem !important;
        line-height: 1.45 !important;
    }

    hr {
        border-color: var(--border-subtle) !important;
        margin: 1rem 0 !important;
    }

    /* Elevated Card Containers */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: linear-gradient(180deg, rgba(23, 32, 51, 0.55) 0%, var(--bg-surface) 100%) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: var(--radius-lg) !important;
        box-shadow: var(--shadow-card) !important;
        padding: 0.25rem 0.4rem !important;
    }

    /* Executive KPI Metric Cards */
    [data-testid="stMetric"] {
        background: linear-gradient(180deg, rgba(23, 32, 51, 0.65) 0%, var(--bg-surface) 100%) !important;
        border: 1px solid var(--border-subtle) !important;
        border-top: 2px solid rgba(99, 102, 241, 0.45) !important;
        border-radius: var(--radius-lg) !important;
        padding: 16px 18px !important;
        box-shadow: var(--shadow-card) !important;
        transition: border-color 0.18s ease, transform 0.18s ease, box-shadow 0.18s ease !important;
        min-height: auto !important;
        overflow: hidden !important;
    }

    [data-testid="stMetric"]:hover {
        border-color: var(--border-accent) !important;
        border-top-color: var(--accent-primary-light) !important;
        transform: translateY(-2px) !important;
        box-shadow: var(--shadow-card-hover) !important;
    }

    [data-testid="stMetricLabel"] p {
        font-size: 0.72rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
        color: var(--text-muted) !important;
        margin: 0 0 4px 0 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    [data-testid="stMetricValue"] div {
        font-size: clamp(1.45rem, 2vw, 1.9rem) !important;
        font-weight: 800 !important;
        color: var(--text-primary) !important;
        letter-spacing: -0.03em !important;
        line-height: 1.15 !important;
        font-variant-numeric: tabular-nums !important;
    }

    [data-testid="stMetricDelta"] {
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        margin-top: 4px !important;
        font-variant-numeric: tabular-nums !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    [data-testid="stMetricDelta"] svg {
        width: 0.85rem !important;
        height: 0.85rem !important;
    }

    /* Plotly Visualization Framing */
    [data-testid="stPlotlyChart"] {
        background: var(--bg-surface) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: var(--radius-lg) !important;
        padding: 14px 16px 8px 16px !important;
        box-shadow: var(--shadow-card) !important;
        transition: border-color 0.18s ease !important;
        overflow: visible !important;
        width: 100% !important;
    }

    [data-testid="stPlotlyChart"]:hover {
        border-color: var(--border-strong) !important;
    }

    /* Segmented Navigation Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: var(--bg-surface) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: var(--radius-md) !important;
        padding: 4px !important;
        gap: 6px !important;
        margin-bottom: 18px !important;
        width: fit-content !important;
        max-width: 100% !important;
    }

    .stTabs [data-baseweb="tab-highlight"],
    .stTabs [data-baseweb="tab-border"] {
        background-color: transparent !important;
        display: none !important;
    }

    .stTabs [data-baseweb="tab"] {
        font-weight: 600 !important;
        font-size: 0.86rem !important;
        padding: 8px 18px !important;
        border-radius: 7px !important;
        color: var(--text-muted) !important;
        border: 1px solid transparent !important;
        background: transparent !important;
        transition: color 0.15s ease, background-color 0.15s ease, border-color 0.15s ease !important;
        height: auto !important;
    }

    .stTabs [data-baseweb="tab"]:hover {
        color: var(--text-primary) !important;
        background: rgba(148, 163, 184, 0.08) !important;
    }

    .stTabs [aria-selected="true"] {
        color: var(--text-primary) !important;
        background: var(--bg-surface-hover) !important;
        border-color: var(--border-strong) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28) !important;
    }

    .stTabs [data-baseweb="tab"]:focus-visible {
        outline: none !important;
        box-shadow: var(--focus-ring) !important;
    }

    /* Sidebar Architecture */
    [data-testid="stSidebar"] {
        background-color: var(--bg-sidebar) !important;
        border-right: 1px solid var(--border-subtle) !important;
    }

    [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--bg-surface) !important;
        border-radius: var(--radius-md) !important;
        box-shadow: none !important;
    }

    [data-testid="stSidebar"] .stProgress > div > div > div > div {
        background: linear-gradient(90deg, var(--accent-primary) 0%, var(--accent-sky) 100%) !important;
        border-radius: 999px !important;
    }

    [data-testid="stSidebar"] .stProgress > div > div > div {
        background-color: rgba(148, 163, 184, 0.16) !important;
        border-radius: 999px !important;
    }

    /* Buttons & Download Controls */
    .stButton > button,
    .stDownloadButton > button {
        background-color: var(--bg-surface-elevated) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-strong) !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
        padding: 0.42rem 0.85rem !important;
        transition: background-color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease, transform 0.12s ease !important;
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover {
        background-color: var(--bg-surface-hover) !important;
        border-color: var(--accent-primary) !important;
        color: #FFFFFF !important;
        box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.35), 0 4px 12px rgba(99, 102, 241, 0.18) !important;
    }

    .stButton > button:active,
    .stDownloadButton > button:active {
        transform: translateY(1px) !important;
    }

    .stButton > button:focus-visible,
    .stDownloadButton > button:focus-visible {
        outline: none !important;
        box-shadow: var(--focus-ring) !important;
    }

    /* Inputs, Selectboxes, Date Pickers & Multiselect Tags */
    [data-baseweb="select"] > div,
    [data-baseweb="input"] > div,
    [data-testid="stDateInput"] input {
        background-color: var(--bg-surface) !important;
        border-color: var(--border-strong) !important;
        border-radius: var(--radius-sm) !important;
        color: var(--text-primary) !important;
        font-size: 0.84rem !important;
    }

    [data-baseweb="select"] > div:focus-within,
    [data-baseweb="input"] > div:focus-within {
        border-color: var(--accent-primary) !important;
        box-shadow: 0 0 0 1px var(--accent-primary) !important;
    }

    [data-baseweb="tag"] {
        background-color: rgba(99, 102, 241, 0.18) !important;
        border: 1px solid rgba(99, 102, 241, 0.42) !important;
        border-radius: 6px !important;
        color: var(--text-primary) !important;
        font-size: 0.76rem !important;
        font-weight: 600 !important;
    }

    /* DataFrames & Tables */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--border-subtle) !important;
        border-radius: var(--radius-md) !important;
        overflow: hidden !important;
        font-variant-numeric: tabular-nums !important;
    }

    /* Expanders */
    [data-testid="stExpander"] {
        background-color: var(--bg-surface) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: var(--radius-md) !important;
        overflow: hidden !important;
    }

    [data-testid="stExpander"] summary:hover {
        color: var(--accent-primary-light) !important;
    }

    /* AI Copilot Chat Bubbles & Input */
    [data-testid="stChatMessage"] {
        background-color: var(--bg-surface) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: var(--radius-lg) !important;
        padding: 1rem 1.15rem !important;
        margin-bottom: 0.75rem !important;
        box-shadow: var(--shadow-card) !important;
    }

    [data-testid="stChatInput"] textarea {
        background-color: var(--bg-surface) !important;
        color: var(--text-primary) !important;
        font-family: var(--font-sans) !important;
        font-size: 0.9rem !important;
    }

    [data-testid="stChatInput"] > div {
        border: 1px solid var(--border-strong) !important;
        border-radius: var(--radius-md) !important;
        background-color: var(--bg-surface) !important;
    }

    [data-testid="stChatInput"] > div:focus-within {
        border-color: var(--accent-primary) !important;
        box-shadow: 0 0 0 1px var(--accent-primary) !important;
    }

    /* Status Alerts */
    [data-testid="stAlert"] {
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--border-subtle) !important;
    }

    /* Scrollbars */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: var(--bg-canvas);
    }
    ::-webkit-scrollbar-thumb {
        background: #273449;
        border-radius: 999px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #3B4C68;
    }

    /* Responsive Breakpoints & Flex Wrapping */
    @media (max-width: 1100px) {
        .block-container {
            padding-left: 1.25rem !important;
            padding-right: 1.25rem !important;
        }
        /* Wrap 4 KPI cards into a 2x2 grid on medium screens */
        [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] [data-testid="stMetric"]) {
            flex-wrap: wrap !important;
            gap: 12px !important;
        }
        [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] [data-testid="stMetric"]) > [data-testid="column"] {
            flex: 1 1 calc(50% - 12px) !important;
            min-width: calc(50% - 12px) !important;
            margin-bottom: 0.5rem !important;
        }
        /* Stack 2-column chart grids vertically so charts are never squished */
        [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] [data-testid="stPlotlyChart"]) {
            flex-wrap: wrap !important;
            gap: 16px !important;
        }
        [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] [data-testid="stPlotlyChart"]) > [data-testid="column"] {
            flex: 1 1 100% !important;
            min-width: 100% !important;
            margin-bottom: 0.75rem !important;
        }
        [data-testid="stMetricValue"] div {
            font-size: 1.6rem !important;
        }
    }

    @media (max-width: 640px) {
        .block-container {
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
            padding-top: 1rem !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="column"] {
            flex: 1 1 100% !important;
            min-width: 100% !important;
            margin-bottom: 0.75rem !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            width: 100% !important;
        }
        .stTabs [data-baseweb="tab"] {
            flex: 1 1 auto !important;
            justify-content: center !important;
            padding: 8px 10px !important;
            font-size: 0.8rem !important;
        }
        [data-testid="stMetric"] {
            padding: 12px 14px !important;
        }
        [data-testid="stMetricValue"] div {
            font-size: 1.45rem !important;
        }
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
        head_left, head_right = st.columns([2.6, 1.8], gap="medium")
        with head_left:
            st.caption("THE CITY OF NEW YORK · EXECUTIVE OPERATIONS CENTER")
            st.subheader("NYC 311 Operations & Analytics Platform")
            st.caption(
                "Continuous real-time monitoring of civic requests, agency SLA resolution performance, and natural language analytics."
            )
        with head_right:
            t1, t2 = st.columns(2, gap="small")
            with t1:
                st.caption("WAREHOUSE STATE")
                st.markdown("**● Live Ingest**")
                st.caption(formatted_synced)
            with t2:
                st.caption("ACTIVE RETENTION")
                st.markdown(f"**{total_records:,}** rows")
                st.caption(f"{pass_rate:.1f}% Quality Pass")

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

        # Band 1: Executive KPI Summary Strip
        render_executive_kpis(kpis)

        # Band 2: Primary Volume & Rolling Trend Hero
        st.markdown("#### Ingestion Velocity & Rolling Trend")
        st.caption("Daily civic request volume paired with 7-day moving average to surface sustained demand shifts.")
        render_volume_trend_chart(trend_df)

        # Band 3: Complaint Taxonomy & Agency SLA Matrix (Balanced 50/50 Grid)
        st.markdown("#### Demand Taxonomy & Agency SLA Efficiency")
        st.caption("Leading complaint categories alongside multi-dimensional agency SLA compliance and turnaround duration.")
        col_types, col_matrix = st.columns([1, 1], gap="medium")
        with col_types:
            render_top_complaints_chart(top_df)
        with col_matrix:
            render_agency_performance_matrix(agency_df)

        # Band 4: Operational Intake & Cadence (Full-Width 50/50 Split)
        st.markdown("#### Intake Channels & Operational Cadence")
        st.caption("Submission channel share and weekday versus weekend volume and resolution dynamics.")
        render_operational_channels_chart(
            channel_data["channels"],
            channel_data["weekday_vs_weekend"]
        )

        # Band 5: Geographic & Spatial Intelligence
        st.markdown("#### Borough, ZIP Code & Geospatial Intelligence")
        st.caption("Regional complaint concentration, resolution speed disparities, and geospatial cluster density.")
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