"""
Sidebar Filter Controls for NYC 311 Executive Analytics.
Provides reactive global filtering across Date Range, Borough, Agency,
Complaint Category, and Ticket Status with quick presets and instant reset capability.
"""

import datetime
from typing import Dict, Any, List, Optional
import streamlit as st


def render_sidebar_filters(filter_options: Dict[str, Any]) -> Dict[str, Any]:
    """
    Render global filter controls in the Streamlit sidebar with executive presets
    and return a structured filter dictionary for SQL query compilation.
    """
    # 1. System Architecture Telemetry Card
    st.sidebar.markdown("""
    <div class="sidebar-telemetry-box">
        <div class="telemetry-title">
            <span class="telemetry-dot"></span> WAREHOUSE TELEMETRY
        </div>
        <div class="telemetry-item">
            <span class="telemetry-lbl">Cluster</span>
            <span class="telemetry-val">Supabase PostgreSQL 17</span>
        </div>
        <div class="telemetry-item">
            <span class="telemetry-lbl">Policy</span>
            <span class="telemetry-val">30-Day Rolling Retention</span>
        </div>
        <div class="telemetry-item">
            <span class="telemetry-lbl">Security</span>
            <span class="telemetry-val">AST Read-Only Enforced</span>
        </div>
        <div class="telemetry-storage-track">
            <div class="telemetry-storage-label">
                <span>Free Tier Quota</span>
                <span class="telemetry-storage-pct">32.2% (161 / 500 MB)</span>
            </div>
            <div class="telemetry-storage-bar">
                <div class="telemetry-storage-fill" style="width: 32.2%;"></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    st.sidebar.markdown("### 🔍 Global Analytical Filters")

    # Initialize session state for filter widgets if not present
    if "filter_date_range_picker" not in st.session_state:
        st.session_state["filter_date_range_picker"] = (filter_options["min_date"], filter_options["max_date"])
    if "filter_boroughs_widget" not in st.session_state:
        st.session_state["filter_boroughs_widget"] = []
    if "filter_agencies_widget" not in st.session_state:
        st.session_state["filter_agencies_widget"] = []
    if "filter_categories_widget" not in st.session_state:
        st.session_state["filter_categories_widget"] = []
    if "filter_statuses_widget" not in st.session_state:
        st.session_state["filter_statuses_widget"] = []

    # Quick Date Range Presets
    st.sidebar.markdown("<span style='font-size: 0.75rem; font-weight: 700; color: #64748B;'>DATE PRESETS</span>", unsafe_allow_html=True)
    p_col1, p_col2, p_col3 = st.sidebar.columns(3)
    max_d = filter_options["max_date"]

    with p_col1:
        if st.button("All Days", key="preset_all", use_container_width=True, help="Full available 30-day window"):
            st.session_state["filter_date_range_picker"] = (filter_options["min_date"], filter_options["max_date"])
            st.rerun()

    with p_col2:
        if st.button("Last 14D", key="preset_14d", use_container_width=True, help="Last 14 calendar days"):
            d_14 = max(filter_options["min_date"], max_d - datetime.timedelta(days=14))
            st.session_state["filter_date_range_picker"] = (d_14, max_d)
            st.rerun()

    with p_col3:
        if st.button("Last 7D", key="preset_7d", use_container_width=True, help="Last 7 calendar days"):
            d_7 = max(filter_options["min_date"], max_d - datetime.timedelta(days=7))
            st.session_state["filter_date_range_picker"] = (d_7, max_d)
            st.rerun()

    # Reset button & filter counter header
    col_reset, col_count = st.sidebar.columns([1, 1])
    with col_reset:
        if st.button("🔄 Reset All", use_container_width=True, help="Reset all filters to full NYC dataset"):
            st.session_state["filter_date_range_picker"] = (filter_options["min_date"], filter_options["max_date"])
            st.session_state["filter_boroughs_widget"] = []
            st.session_state["filter_agencies_widget"] = []
            st.session_state["filter_categories_widget"] = []
            st.session_state["filter_statuses_widget"] = []
            st.rerun()

    # 1. Date Range
    date_val = st.sidebar.date_input(
        "📅 Custom Date Range",
        min_value=filter_options["min_date"],
        max_value=filter_options["max_date"],
        key="filter_date_range_picker",
        help="Filter complaints by incident creation date."
    )

    # Handle single or range date return from Streamlit
    if isinstance(date_val, (list, tuple)):
        if len(date_val) == 2:
            selected_date_range = (date_val[0], date_val[1])
        elif len(date_val) == 1:
            selected_date_range = (date_val[0], date_val[0])
        else:
            selected_date_range = (filter_options["min_date"], filter_options["max_date"])
    elif isinstance(date_val, datetime.date):
        selected_date_range = (date_val, date_val)
    else:
        selected_date_range = (filter_options["min_date"], filter_options["max_date"])

    # 2. Borough Filter
    selected_boroughs = st.sidebar.multiselect(
        "🏙️ Borough",
        options=filter_options["boroughs"],
        key="filter_boroughs_widget",
        placeholder="All Boroughs"
    )

    # 3. Agency Filter
    selected_agencies = st.sidebar.multiselect(
        "🏢 Responding Agency",
        options=filter_options["agencies"],
        key="filter_agencies_widget",
        placeholder="All Responding Agencies"
    )

    # 4. Complaint Category Filter
    selected_categories = st.sidebar.multiselect(
        "🏷️ Complaint Category",
        options=filter_options["categories"],
        key="filter_categories_widget",
        placeholder="All Complaint Categories"
    )

    # 5. Status Filter
    selected_statuses = st.sidebar.multiselect(
        "📌 Ticket Status",
        options=filter_options["statuses"],
        key="filter_statuses_widget",
        placeholder="All Statuses"
    )

    # Active filters count badge
    active_filters = 0
    if selected_date_range != (filter_options["min_date"], filter_options["max_date"]):
        active_filters += 1
    if selected_boroughs:
        active_filters += 1
    if selected_agencies:
        active_filters += 1
    if selected_categories:
        active_filters += 1
    if selected_statuses:
        active_filters += 1

    with col_count:
        if active_filters > 0:
            st.markdown(f"<div class='active-filter-pill'>⚡ {active_filters} Active Filter(s)</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='all-data-pill'>● Full NYC Scope</div>", unsafe_allow_html=True)

    st.sidebar.divider()

    return {
        "date_range": selected_date_range,
        "boroughs": selected_boroughs,
        "agencies": selected_agencies,
        "categories": selected_categories,
        "statuses": selected_statuses
    }
