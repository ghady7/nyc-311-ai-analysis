"""
Executive KPI Cards Component for NYC 311 Analytics.
Displays 4 high-level executive cards with modern glassmorphic styling,
progress indicators, period-over-period delta comparison pills, and resilient fallbacks.
"""

from typing import Dict, Any
import streamlit as st


def render_executive_kpis(kpis: Dict[str, Any]) -> None:
    """
    Render 4 executive KPI cards in a modern responsive grid layout:
    1. Total Complaints (with % volume delta)
    2. Closure Rate % (with percentage point delta & progress bar)
    3. SLA Compliance Rate % (with percentage point delta & target marker)
    4. Median & Mean Resolution Time (with duration delta)
    """
    if not isinstance(kpis, dict):
        kpis = {}

    total = int(kpis.get("total_complaints") or 0)
    total_delta = float(kpis.get("total_delta_pct") or 0.0)
    closure_rate = float(kpis.get("closure_rate") or 0.0)
    closure_delta = float(kpis.get("closure_delta") or 0.0)
    sla_rate = float(kpis.get("sla_compliance_rate") or 0.0)
    sla_delta = float(kpis.get("sla_delta") or 0.0)
    median_hours = float(kpis.get("median_resolution_hours") or 0.0)
    avg_hours = float(kpis.get("avg_resolution_hours") or 0.0)
    hours_delta = float(kpis.get("resolution_hours_delta") or 0.0)

    # Format helper for delta badges
    def format_badge(delta_val: float, is_duration: bool = False, is_neutral: bool = False, unit: str = "%") -> str:
        if is_neutral:
            symbol = "●" if delta_val == 0 else ("▲" if delta_val > 0 else "▼")
            return f'<span class="kpi-pill kpi-pill-neutral">{symbol} {abs(delta_val):.1f}{unit}</span>'

        if is_duration:
            # For duration, negative delta (faster) is positive (green), positive (slower) is negative (red)
            if delta_val < 0:
                return f'<span class="kpi-pill kpi-pill-success">▼ {abs(delta_val):.1f} hrs faster</span>'
            elif delta_val > 0:
                return f'<span class="kpi-pill kpi-pill-danger">▲ +{delta_val:.1f} hrs slower</span>'
            return '<span class="kpi-pill kpi-pill-neutral">● 0.0 hrs</span>'

        if delta_val > 0:
            return f'<span class="kpi-pill kpi-pill-success">▲ +{delta_val:.1f}{unit}</span>'
        elif delta_val < 0:
            return f'<span class="kpi-pill kpi-pill-danger">▼ {delta_val:.1f}{unit}</span>'
        return f'<span class="kpi-pill kpi-pill-neutral">● 0.0{unit}</span>'

    badge_total = format_badge(total_delta, is_neutral=True)
    badge_closure = format_badge(closure_delta, unit="% pt")
    badge_sla = format_badge(sla_delta, unit="% pt")
    badge_hours = format_badge(hours_delta, is_duration=True)

    closure_clamped = max(0.0, min(100.0, closure_rate))
    sla_clamped = max(0.0, min(100.0, sla_rate))
    sla_color = "#10B981" if sla_clamped >= 85.0 else ("#F59E0B" if sla_clamped >= 70.0 else "#EF4444")

    cards_html = f"""
    <div class="kpi-grid">
        <!-- Card 1: Municipal Volume -->
        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-tag">MUNICIPAL VOLUME</span>
                <span class="kpi-icon-badge badge-indigo">📋</span>
            </div>
            <div class="kpi-body">
                <div class="kpi-value">{total:,}</div>
            </div>
            <div class="kpi-footer">
                {badge_total}
                <span class="kpi-context">vs prior period</span>
            </div>
        </div>

        <!-- Card 2: Resolution Rate -->
        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-tag">RESOLUTION RATE</span>
                <span class="kpi-icon-badge badge-emerald">✅</span>
            </div>
            <div class="kpi-body">
                <div class="kpi-value">{closure_rate:.1f}%</div>
                <div class="kpi-progress-track">
                    <div class="kpi-progress-fill" style="width: {closure_clamped}%; background: #10B981;"></div>
                </div>
            </div>
            <div class="kpi-footer">
                {badge_closure}
                <span class="kpi-context">Tickets closed</span>
            </div>
        </div>

        <!-- Card 3: SLA Compliance -->
        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-tag">SLA COMPLIANCE</span>
                <span class="kpi-icon-badge badge-sky">⏱️</span>
            </div>
            <div class="kpi-body">
                <div class="kpi-value">{sla_rate:.1f}%</div>
                <div class="kpi-progress-track">
                    <div class="kpi-progress-fill" style="width: {sla_clamped}%; background: {sla_color};"></div>
                </div>
            </div>
            <div class="kpi-footer">
                {badge_sla}
                <span class="kpi-context">Target: &ge;85.0%</span>
            </div>
        </div>

        <!-- Card 4: Speed to Resolve -->
        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-tag">SPEED TO RESOLVE</span>
                <span class="kpi-icon-badge badge-amber">⚡</span>
            </div>
            <div class="kpi-body">
                <div class="kpi-value">{median_hours:.1f} <span class="kpi-unit">hrs</span></div>
            </div>
            <div class="kpi-footer">
                {badge_hours}
                <span class="kpi-context">Mean: {avg_hours:.1f} hrs</span>
            </div>
        </div>
    </div>
    """
    st.markdown(cards_html, unsafe_allow_html=True)
