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

# Unified Enterprise Design System (Apple Frosted Glass & Blue Ambient Theme)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
        /* Apple Ocean Midnight Palette */
        --apple-midnight: #070D1E;
        --apple-navy: #0F1D38;
        --apple-glass-bg: rgba(14, 25, 48, 0.68);
        --apple-glass-elevated: rgba(20, 36, 68, 0.78);
        --apple-glass-hover: rgba(28, 48, 88, 0.88);

        /* Specular Mirror Rim Reflections */
        --mirror-specular-top: rgba(255, 255, 255, 0.42);
        --mirror-specular-border: rgba(255, 255, 255, 0.16);
        --mirror-specular-inner: rgba(255, 255, 255, 0.22);
        --mirror-shadow: 0 16px 40px -8px rgba(0, 10, 32, 0.65), 0 2px 6px 0 rgba(0, 0, 0, 0.3);
        --mirror-shadow-hover: 0 24px 54px -10px rgba(0, 14, 42, 0.75), 0 0 32px -4px rgba(10, 132, 255, 0.35);

        /* Apple System Accent Palette */
        --apple-blue: #0A84FF;
        --apple-blue-glow: rgba(10, 132, 255, 0.35);
        --apple-cyan: #64D2FF;
        --apple-indigo: #5E5CE6;
        --apple-mint: #30D158;
        --apple-amber: #FF9F0A;
        --apple-rose: #FF453A;
        --apple-purple: #BF5AF2;

        /* Apple Typography Tokens */
        --apple-text-primary: #F5F5F7;
        --apple-text-secondary: #D1D1D6;
        --apple-text-muted: #8E8E93;
        --apple-text-dim: #636366;

        /* Apple Radii */
        --radius-xs: 6px;
        --radius-sm: 10px;
        --radius-md: 14px;
        --radius-lg: 20px;
        --radius-pill: 9999px;

        --focus-ring: 0 0 0 2px #070D1E, 0 0 0 4px #0A84FF;

        --font-sans: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Plus Jakarta Sans", "Segoe UI", Roboto, sans-serif;
        --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
    }

    /* Global Canvas & Apple Mesh Illumination */
    html, body, [class*="css"], .stApp {
        font-family: var(--font-sans) !important;
        background-color: var(--apple-midnight) !important;
        background-image:
            radial-gradient(1100px circle at 15% 10%, rgba(10, 132, 255, 0.24) 0%, transparent 60%),
            radial-gradient(900px circle at 85% 85%, rgba(94, 92, 230, 0.20) 0%, transparent 55%),
            radial-gradient(800px circle at 50% 45%, rgba(100, 210, 255, 0.08) 0%, transparent 60%),
            linear-gradient(180deg, #070D1E 0%, #0A1428 50%, #050A16 100%) !important;
        background-attachment: fixed !important;
        color: var(--apple-text-primary) !important;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    code, pre, [data-testid="stCodeBlock"] {
        font-family: var(--font-mono) !important;
        font-variant-numeric: tabular-nums !important;
    }

    /* Chrome Cleanup */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    [data-testid="stDecoration"] { display: none !important; }
    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    /* Main Container Rhythm */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 3.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 1540px !important;
    }

    /* Prevent Flex / Grid Overflow on Charts & Tables */
    [data-testid="column"],
    [data-testid="stColumn"],
    [data-testid="stHorizontalBlock"] > div {
        min-width: 0 !important;
    }

    /* Typography Hierarchy */
    h1, h2, h3, h4 {
        color: var(--apple-text-primary) !important;
        letter-spacing: -0.025em !important;
        font-weight: 700 !important;
    }

    h3 {
        font-size: 1.4rem !important;
        line-height: 1.25 !important;
        margin-bottom: 0.25rem !important;
        font-weight: 800 !important;
    }

    h4 {
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.015em !important;
        margin-top: 1.1rem !important;
        margin-bottom: 0.2rem !important;
        color: #FFFFFF !important;
    }

    [data-testid="stCaptionContainer"] {
        color: var(--apple-text-muted) !important;
        font-size: 0.8rem !important;
        line-height: 1.45 !important;
        letter-spacing: -0.005em !important;
    }

    hr {
        border-color: rgba(255, 255, 255, 0.1) !important;
        margin: 1.25rem 0 !important;
    }

    /* Mirror Glass Card Containers */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.015) 100%), var(--apple-glass-bg) !important;
        backdrop-filter: blur(28px) saturate(210%) !important;
        -webkit-backdrop-filter: blur(28px) saturate(210%) !important;
        border: 1px solid var(--mirror-specular-border) !important;
        border-top: 1px solid var(--mirror-specular-top) !important;
        border-radius: var(--radius-lg) !important;
        box-shadow: inset 0 1px 1px 0 var(--mirror-specular-inner), var(--mirror-shadow) !important;
        padding: 0.4rem 0.55rem !important;
        transition: border-color 0.22s ease, box-shadow 0.22s ease !important;
    }

    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: rgba(130, 195, 255, 0.35) !important;
        border-top-color: rgba(255, 255, 255, 0.6) !important;
    }

    /* Apple Frosted Mirror KPI Metric Cards */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.10) 0%, rgba(255, 255, 255, 0.02) 100%), var(--apple-glass-bg) !important;
        backdrop-filter: blur(30px) saturate(210%) !important;
        -webkit-backdrop-filter: blur(30px) saturate(210%) !important;
        border: 1px solid var(--mirror-specular-border) !important;
        border-top: 2px solid var(--mirror-specular-top) !important;
        border-radius: var(--radius-lg) !important;
        padding: 18px 20px !important;
        box-shadow: inset 0 1px 1px 0 var(--mirror-specular-inner), var(--mirror-shadow) !important;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
        min-height: auto !important;
        overflow: hidden !important;
        position: relative !important;
    }

    [data-testid="stMetric"]:hover {
        border-color: rgba(130, 195, 255, 0.45) !important;
        border-top-color: rgba(255, 255, 255, 0.8) !important;
        transform: translateY(-3px) !important;
        box-shadow: inset 0 1px 2px 0 rgba(255, 255, 255, 0.45), var(--mirror-shadow-hover) !important;
    }

    [data-testid="stMetricLabel"] p {
        font-size: 0.74rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
        color: var(--apple-text-muted) !important;
        margin: 0 0 5px 0 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    [data-testid="stMetricValue"] div {
        font-size: clamp(1.5rem, 2.1vw, 2.05rem) !important;
        font-weight: 800 !important;
        color: #FFFFFF !important;
        letter-spacing: -0.035em !important;
        line-height: 1.15 !important;
        font-variant-numeric: tabular-nums !important;
        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.3) !important;
    }

    [data-testid="stMetricDelta"] {
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        margin-top: 5px !important;
        font-variant-numeric: tabular-nums !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    [data-testid="stMetricDelta"] svg {
        width: 0.85rem !important;
        height: 0.85rem !important;
    }

    /* Plotly Visualization Framing - Mirror Liquid Glass */
    [data-testid="stPlotlyChart"] {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.07) 0%, rgba(255, 255, 255, 0.015) 100%), var(--apple-glass-bg) !important;
        backdrop-filter: blur(28px) saturate(210%) !important;
        -webkit-backdrop-filter: blur(28px) saturate(210%) !important;
        border: 1px solid var(--mirror-specular-border) !important;
        border-top: 1.5px solid var(--mirror-specular-top) !important;
        border-radius: var(--radius-lg) !important;
        padding: 16px 18px 10px 18px !important;
        box-shadow: inset 0 1px 1px 0 var(--mirror-specular-inner), var(--mirror-shadow) !important;
        transition: all 0.24s cubic-bezier(0.16, 1, 0.3, 1) !important;
        overflow: visible !important;
        width: 100% !important;
    }

    [data-testid="stPlotlyChart"]:hover {
        border-color: rgba(130, 195, 255, 0.4) !important;
        border-top-color: rgba(255, 255, 255, 0.7) !important;
        box-shadow: inset 0 1px 2px 0 rgba(255, 255, 255, 0.35), var(--mirror-shadow-hover) !important;
    }

    /* Apple Capsule Segmented Navigation Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(14, 25, 48, 0.72) !important;
        backdrop-filter: blur(24px) saturate(200%) !important;
        -webkit-backdrop-filter: blur(24px) saturate(200%) !important;
        border: 1px solid rgba(255, 255, 255, 0.14) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: var(--radius-pill) !important;
        padding: 5px !important;
        gap: 6px !important;
        margin-bottom: 22px !important;
        width: fit-content !important;
        max-width: 100% !important;
        box-shadow: inset 0 1px 1px 0 rgba(255, 255, 255, 0.2), 0 8px 24px rgba(0, 0, 0, 0.35) !important;
    }

    .stTabs [data-baseweb="tab-highlight"],
    .stTabs [data-baseweb="tab-border"] {
        background-color: transparent !important;
        display: none !important;
    }

    .stTabs [data-baseweb="tab"] {
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        padding: 8px 22px !important;
        border-radius: var(--radius-pill) !important;
        color: var(--apple-text-secondary) !important;
        border: 1px solid transparent !important;
        background: transparent !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
        height: auto !important;
    }

    .stTabs [data-baseweb="tab"]:hover {
        color: #FFFFFF !important;
        background: rgba(255, 255, 255, 0.08) !important;
    }

    .stTabs [aria-selected="true"] {
        color: #FFFFFF !important;
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.22) 0%, rgba(255, 255, 255, 0.06) 100%), rgba(10, 132, 255, 0.55) !important;
        border: 1px solid rgba(255, 255, 255, 0.32) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.6) !important;
        box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.4), 0 4px 18px rgba(10, 132, 255, 0.42) !important;
    }

    .stTabs [data-baseweb="tab"]:focus-visible {
        outline: none !important;
        box-shadow: var(--focus-ring) !important;
    }

    /* Apple Translucent Frosted Sidebar */
    [data-testid="stSidebar"] {
        background-color: rgba(8, 16, 32, 0.85) !important;
        backdrop-filter: blur(32px) saturate(210%) !important;
        -webkit-backdrop-filter: blur(32px) saturate(210%) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.12) !important;
        box-shadow: 10px 0 36px rgba(0, 0, 0, 0.4) !important;
    }

    [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(14, 25, 48, 0.65) !important;
        border-radius: var(--radius-md) !important;
        border-color: rgba(255, 255, 255, 0.12) !important;
        border-top-color: rgba(255, 255, 255, 0.25) !important;
    }

    [data-testid="stSidebar"] .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #0A84FF 0%, #64D2FF 100%) !important;
        border-radius: 999px !important;
        box-shadow: 0 0 12px rgba(10, 132, 255, 0.5) !important;
    }

    [data-testid="stSidebar"] .stProgress > div > div > div {
        background-color: rgba(255, 255, 255, 0.1) !important;
        border-radius: 999px !important;
    }

    /* Buttons & Download Controls - Specular Glass */
    .stButton > button,
    .stDownloadButton > button {
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.14) 0%, rgba(255, 255, 255, 0.04) 100%), rgba(20, 36, 70, 0.8) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.45) !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 600 !important;
        font-size: 0.84rem !important;
        padding: 0.45rem 0.95rem !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.25), 0 4px 12px rgba(0, 0, 0, 0.25) !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover {
        background: linear-gradient(180deg, rgba(10, 132, 255, 0.45) 0%, rgba(10, 132, 255, 0.2) 100%), rgba(22, 44, 88, 0.9) !important;
        border-color: rgba(100, 210, 255, 0.55) !important;
        border-top-color: rgba(255, 255, 255, 0.75) !important;
        box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.4), 0 0 20px rgba(10, 132, 255, 0.45), 0 6px 16px rgba(0, 0, 0, 0.3) !important;
        transform: translateY(-1px) !important;
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
        background-color: rgba(14, 25, 48, 0.8) !important;
        border: 1px solid rgba(255, 255, 255, 0.16) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.28) !important;
        border-radius: var(--radius-sm) !important;
        color: var(--apple-text-primary) !important;
        font-size: 0.86rem !important;
        box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.25) !important;
    }

    [data-baseweb="select"] > div:focus-within,
    [data-baseweb="input"] > div:focus-within {
        border-color: var(--apple-blue) !important;
        box-shadow: 0 0 0 3px rgba(10, 132, 255, 0.32) !important;
    }

    [data-baseweb="tag"] {
        background-color: rgba(10, 132, 255, 0.24) !important;
        border: 1px solid rgba(100, 210, 255, 0.45) !important;
        border-radius: 8px !important;
        color: #FFFFFF !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
    }

    /* DataFrames & Tables */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--mirror-specular-border) !important;
        border-top: 1.5px solid var(--mirror-specular-top) !important;
        border-radius: var(--radius-md) !important;
        overflow: hidden !important;
        font-variant-numeric: tabular-nums !important;
        box-shadow: var(--mirror-shadow) !important;
    }

    /* Expanders */
    [data-testid="stExpander"] {
        background-color: rgba(14, 25, 48, 0.7) !important;
        border: 1px solid var(--mirror-specular-border) !important;
        border-top: 1px solid var(--mirror-specular-top) !important;
        border-radius: var(--radius-md) !important;
        overflow: hidden !important;
        box-shadow: var(--mirror-shadow) !important;
    }

    [data-testid="stExpander"] summary:hover {
        color: var(--apple-cyan) !important;
    }

    /* AI Copilot Chat Bubbles & Input */
    [data-testid="stChatMessage"] {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.02) 100%), var(--apple-glass-bg) !important;
        backdrop-filter: blur(28px) saturate(210%) !important;
        -webkit-backdrop-filter: blur(28px) saturate(210%) !important;
        border: 1px solid var(--mirror-specular-border) !important;
        border-top: 1px solid var(--mirror-specular-top) !important;
        border-radius: var(--radius-lg) !important;
        padding: 1.1rem 1.25rem !important;
        margin-bottom: 0.85rem !important;
        box-shadow: inset 0 1px 1px 0 var(--mirror-specular-inner), var(--mirror-shadow) !important;
    }

    [data-testid="stChatInput"] textarea {
        background-color: transparent !important;
        color: var(--apple-text-primary) !important;
        font-family: var(--font-sans) !important;
        font-size: 0.92rem !important;
    }

    [data-testid="stChatInput"] > div {
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.35) !important;
        border-radius: var(--radius-pill) !important;
        background: rgba(14, 25, 48, 0.8) !important;
        backdrop-filter: blur(24px) !important;
        box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.2), 0 8px 24px rgba(0, 0, 0, 0.35) !important;
        padding: 4px 8px !important;
    }

    [data-testid="stChatInput"] > div:focus-within {
        border-color: var(--apple-blue) !important;
        box-shadow: 0 0 0 3px rgba(10, 132, 255, 0.35), 0 8px 24px rgba(0, 0, 0, 0.35) !important;
    }

    /* Status Alerts */
    [data-testid="stAlert"] {
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--mirror-specular-border) !important;
        backdrop-filter: blur(20px) !important;
    }

    /* Scrollbars */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: transparent;
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.22);
        border-radius: 999px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(255, 255, 255, 0.38);
    }

    /* Responsive Breakpoints & Flex Wrapping */
    @media (max-width: 1100px) {
        .block-container {
            padding-left: 1.25rem !important;
            padding-right: 1.25rem !important;
        }
        [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] [data-testid="stMetric"]) {
            flex-wrap: wrap !important;
            gap: 14px !important;
        }
        [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] [data-testid="stMetric"]) > [data-testid="column"] {
            flex: 1 1 calc(50% - 14px) !important;
            min-width: calc(50% - 14px) !important;
            margin-bottom: 0.5rem !important;
        }
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
            font-size: 1.65rem !important;
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
            padding: 8px 12px !important;
            font-size: 0.82rem !important;
        }
        [data-testid="stMetric"] {
            padding: 14px 16px !important;
        }
        [data-testid="stMetricValue"] div {
            font-size: 1.5rem !important;
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