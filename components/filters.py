"""
Sidebar Filter Controls for NYC 311 Executive Analytics.
Provides reactive global filtering across Date Range, Borough, Agency,
Complaint Category, and Ticket Status with instant reset capability.
"""

import datetime
from typing import Dict, Any, List, Optional
import streamlit as st


def render_sidebar_filters(filter_options: Dict[str, Any]) -> Dict[str, Any]:
    """
    Render global filter controls in the Streamlit sidebar and return
    a structured filter dictionary for SQL query compilation.
    """
    st.sidebar.markdown("## 🔍 Global Filters")
    st.sidebar.caption("Filter all KPIs and visual analytics dynamically.")

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

    # Reset button
    col_reset, col_count = st.sidebar.columns([1, 1])
    with col_reset:
        if st.button("🔄 Reset All", use_container_width=True):
            st.session_state["filter_date_range_picker"] = (filter_options["min_date"], filter_options["max_date"])
            st.session_state["filter_boroughs_widget"] = []
            st.session_state["filter_agencies_widget"] = []
            st.session_state["filter_categories_widget"] = []
            st.session_state["filter_statuses_widget"] = []
            st.rerun()

    # 1. Date Range
    date_val = st.sidebar.date_input(
        "📅 Date Range",
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
        placeholder="All Agencies"
    )

    # 4. Complaint Category Filter
    selected_categories = st.sidebar.multiselect(
        "🏷️ Complaint Category",
        options=filter_options["categories"],
        key="filter_categories_widget",
        placeholder="All Categories"
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
            st.markdown(f"<span style='color: #2b6cb0; font-weight: 600; font-size: 0.85rem;'>⚡ {active_filters} active filter(s)</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span style='color: #718096; font-size: 0.85rem;'>All NYC Data</span>", unsafe_allow_html=True)

    st.sidebar.divider()

    return {
        "date_range": selected_date_range,
        "boroughs": selected_boroughs,
        "agencies": selected_agencies,
        "categories": selected_categories,
        "statuses": selected_statuses
    }
