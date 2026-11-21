"""
Executive KPI Cards Component for NYC 311 Analytics.
Displays 4 high-level executive cards with period-over-period delta comparisons,
custom card styling, and performance indicators.
"""

from typing import Dict, Any
import streamlit as st


def render_executive_kpis(kpis: Dict[str, Any]) -> None:
    """
    Render 4 executive KPI cards in a 4-column row:
    1. Total Complaints (with % volume delta)
    2. Closure Rate % (with percentage point delta)
    3. SLA Compliance Rate % (with percentage point delta)
    4. Median & Mean Resolution Time (with hours delta)
    """
    total = int(kpis.get("total_complaints") or 0)
    total_delta = float(kpis.get("total_delta_pct") or 0.0)
    closure_rate = float(kpis.get("closure_rate") or 0.0)
    closure_delta = float(kpis.get("closure_delta") or 0.0)
    sla_rate = float(kpis.get("sla_compliance_rate") or 0.0)
    sla_delta = float(kpis.get("sla_delta") or 0.0)
    median_hours = float(kpis.get("median_resolution_hours") or 0.0)
    avg_hours = float(kpis.get("avg_resolution_hours") or 0.0)
    hours_delta = float(kpis.get("resolution_hours_delta") or 0.0)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="📋 Total Complaints",
            value=f"{total:,}",
            delta=f"{total_delta:+.1f}% vs prior period",
            delta_color="off",
            help="Total 311 service requests recorded within selected filters."
        )

    with col2:
        st.metric(
            label="✅ Closure Rate",
            value=f"{closure_rate:.1f}%",
            delta=f"{closure_delta:+.1f}% pt",
            delta_color="normal",
            help="Percentage of tickets with status 'Closed' (is_closed = true)."
        )

    with col3:
        st.metric(
            label="⏱️ SLA Compliance Rate",
            value=f"{sla_rate:.1f}%",
            delta=f"{sla_delta:+.1f}% pt",
            delta_color="normal",
            help="Percentage of closed tickets resolved before SLA due timestamp."
        )

    with col4:
        # For resolution time, a negative delta (faster resolution) is positive
        st.metric(
            label="⏳ Resolution Time (Median)",
            value=f"{median_hours:.1f} hrs",
            delta=f"Mean: {avg_hours:.1f} hrs ({hours_delta:+.1f} hrs)",
            delta_color="inverse",
            help="Median resolution time for closed tickets. Lower duration indicates faster city response."
        )
