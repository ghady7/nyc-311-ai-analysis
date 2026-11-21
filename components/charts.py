"""
Interactive Plotly Visual Analytics Charts for NYC 311 Dashboard.
Implements executive-styled visualizations:
- Volume Trend with 7-Day Rolling Average (Combo Bar + Line)
- Top Complaint Categories & Types (Horizontal Bar)
- Agency Performance Matrix (Bubble Scatter)
- Geographic Breakdown by Borough & Top Zip Codes + Density Map
- Operational Channels & Weekday/Weekend Breakdown (Donut + Grouped Bar)
"""

from typing import Dict, Any, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# Color Palette: Corporate NYC Analytics Theme
PALETTE = {
    "primary": "#1F497D",      # Deep Navy
    "secondary": "#2B6CB0",    # Vibrant Blue
    "accent_orange": "#DD6B20",# Warm Amber/Orange
    "accent_green": "#2F855A", # Forest Green
    "accent_red": "#C53030",   # Crimson
    "accent_purple": "#6B46C1",# Slate Purple
    "light_bg": "#F7FAFC",     # Light Grey Background
    "grid_color": "#E2E8F0"    # Subtle Gridline
}

CHART_LAYOUT_DEFAULTS = dict(
    font=dict(family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", size=12),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=40, r=20, t=40, b=40),
    hoverlabel=dict(bgcolor="white", font_size=12, font_family="sans-serif")
)


def render_volume_trend_chart(df: pd.DataFrame) -> None:
    """
    Render daily complaint volume combo chart:
    - Bar chart for daily complaint count
    - Smooth line for 7-day rolling average
    """
    if df.empty:
        st.info("No volume trend data available for current filter selection.")
        return

    fig = go.Figure()

    # Daily Volume Bars
    fig.add_trace(
        go.Bar(
            x=df["full_date"],
            y=df["complaint_volume"],
            name="Daily Volume",
            marker_color=PALETTE["secondary"],
            opacity=0.6,
            hovertemplate="<b>Date:</b> %{x|%b %d, %Y}<br><b>Daily Complaints:</b> %{y:,}<extra></extra>"
        )
    )

    # 7-Day Rolling Average Line
    if "rolling_7d_avg" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["full_date"],
                y=df["rolling_7d_avg"],
                name="7-Day Rolling Avg",
                mode="lines+markers",
                line=dict(color=PALETTE["accent_orange"], width=3),
                marker=dict(size=5, color=PALETTE["accent_orange"]),
                hovertemplate="<b>7-Day Moving Avg:</b> %{y:,.1f}<extra></extra>"
            )
        )

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        title="<b>Daily Complaint Volume & 7-Day Moving Average</b>",
        xaxis=dict(
            title="",
            showgrid=True,
            gridcolor=PALETTE["grid_color"],
            tickformat="%b %d"
        ),
        yaxis=dict(
            title="Service Requests",
            showgrid=True,
            gridcolor=PALETTE["grid_color"],
            rangemode="tozero"
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        height=380
    )

    st.plotly_chart(fig, use_container_width=True)


def render_top_complaints_chart(df: pd.DataFrame) -> None:
    """
    Render horizontal bar chart of top complaint types and categories.
    """
    if df.empty:
        st.info("No complaint type data available for current filter selection.")
        return

    plot_df = df.copy().head(12)
    plot_df = plot_df.sort_values(by="complaint_count", ascending=True)

    fig = px.bar(
        plot_df,
        x="complaint_count",
        y="complaint_type",
        color="complaint_category",
        orientation="h",
        title="<b>Top Complaint Types by Volume & Category</b>",
        labels={"complaint_count": "Number of Complaints", "complaint_type": "", "complaint_category": "Category"},
        color_discrete_sequence=[
            PALETTE["primary"], PALETTE["secondary"], PALETTE["accent_orange"],
            PALETTE["accent_green"], PALETTE["accent_purple"], PALETTE["accent_red"]
        ]
    )

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        xaxis=dict(showgrid=True, gridcolor=PALETTE["grid_color"]),
        yaxis=dict(showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400
    )
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>Category: %{data.name}<br>Volume: %{x:,}<extra></extra>"
    )

    st.plotly_chart(fig, use_container_width=True)


def render_agency_performance_matrix(df: pd.DataFrame) -> None:
    """
    Render Agency Performance Matrix:
    - X-axis: Total Complaints Volume
    - Y-axis: SLA Compliance Rate (%)
    - Bubble Size: Average Resolution Time (Hours)
    """
    if df.empty:
        st.info("No agency performance records available for current filter selection.")
        return

    plot_df = df.copy()
    plot_df["avg_resolution_hours"] = pd.to_numeric(plot_df.get("avg_resolution_hours"), errors="coerce").fillna(0.0)
    plot_df["sla_compliance_rate"] = pd.to_numeric(plot_df.get("sla_compliance_rate"), errors="coerce").fillna(0.0)
    plot_df["closure_rate"] = pd.to_numeric(plot_df.get("closure_rate"), errors="coerce").fillna(0.0)
    plot_df["total_complaints"] = pd.to_numeric(plot_df.get("total_complaints"), errors="coerce").fillna(0).astype(int)
    plot_df["agency_name"] = plot_df.get("agency_name", "").fillna("Unknown")
    plot_df["agency_code"] = plot_df.get("agency_code", "").fillna("N/A")
    # Use a non-zero marker size for bubble scaling so bubbles with 0.0 hrs are still visible
    plot_df["bubble_size"] = plot_df["avg_resolution_hours"].clip(lower=2.0)

    fig = px.scatter(
        plot_df,
        x="total_complaints",
        y="sla_compliance_rate",
        size="bubble_size",
        color="avg_resolution_hours",
        text="agency_code",
        title="<b>Agency Performance Matrix (Volume vs. SLA Compliance % vs. Avg Duration)</b>",
        labels={
            "total_complaints": "Total Ticket Volume",
            "sla_compliance_rate": "SLA Compliance Rate (%)",
            "avg_resolution_hours": "Avg Resolution Hours",
            "agency_code": "Agency"
        },
        color_continuous_scale="Viridis_r",
        size_max=35
    )

    fig.update_traces(
        textposition="top center",
        hovertemplate=(
            "<b>%{customdata[0]}</b> (%{text})<br>"
            "Total Volume: %{x:,}<br>"
            "SLA Compliance: %{y:.1f}%<br>"
            "Avg Resolution: %{customdata[2]:.1f} hrs<br>"
            "Closure Rate: %{customdata[1]:.1f}%<extra></extra>"
        ),
        customdata=plot_df[["agency_name", "closure_rate", "avg_resolution_hours"]].values
    )

    fig.update_layout(
        **CHART_LAYOUT_DEFAULTS,
        xaxis=dict(showgrid=True, gridcolor=PALETTE["grid_color"]),
        yaxis=dict(showgrid=True, gridcolor=PALETTE["grid_color"], range=[-5, 105]),
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)


def render_geographic_charts(
    borough_df: pd.DataFrame,
    zip_df: pd.DataFrame,
    cluster_df: Optional[pd.DataFrame] = None
) -> None:
    """
    Render Geographic breakdown:
    - Tab 1: Borough volume & avg resolution hours
    - Tab 2: Top 10 Incident Zip Codes
    - Tab 3: Geospatial Density Map (Scattermapbox / OpenStreetMap)
    """
    tab_borough, tab_zip, tab_map = st.tabs([
        "🏙️ Borough Comparison",
        "📮 Top Incident Zip Codes",
        "🗺️ Geographic Density Map"
    ])

    with tab_borough:
        if borough_df.empty:
            st.info("No borough data available.")
        else:
            fig_b = make_subplots(specs=[[{"secondary_y": True}]])

            fig_b.add_trace(
                go.Bar(
                    x=borough_df["borough"],
                    y=borough_df["total_complaints"],
                    name="Complaint Volume",
                    marker_color=PALETTE["primary"],
                    hovertemplate="<b>%{x}</b><br>Volume: %{y:,}<extra></extra>"
                ),
                secondary_y=False
            )

            fig_b.add_trace(
                go.Scatter(
                    x=borough_df["borough"],
                    y=borough_df["avg_resolution_hours"],
                    name="Avg Resolution (Hrs)",
                    mode="lines+markers",
                    line=dict(color=PALETTE["accent_orange"], width=3),
                    marker=dict(size=8, color=PALETTE["accent_orange"]),
                    hovertemplate="<b>%{x}</b><br>Avg Resolution: %{y:.1f} hrs<extra></extra>"
                ),
                secondary_y=True
            )

            fig_b.update_layout(
                **CHART_LAYOUT_DEFAULTS,
                title="<b>Complaint Volume & Average Resolution Time by Borough</b>",
                xaxis=dict(showgrid=False),
                yaxis=dict(title="Complaints", showgrid=True, gridcolor=PALETTE["grid_color"]),
                yaxis2=dict(title="Avg Resolution (Hours)", showgrid=False, rangemode="tozero"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=380
            )

            st.plotly_chart(fig_b, use_container_width=True)

    with tab_zip:
        if zip_df.empty:
            st.info("No ZIP code data available.")
        else:
            plot_zip = zip_df.sort_values(by="complaint_count", ascending=True)
            fig_z = px.bar(
                plot_zip,
                x="complaint_count",
                y="incident_zip",
                color="borough",
                orientation="h",
                title="<b>Top 10 Incident Zip Codes by Volume</b>",
                labels={"complaint_count": "Complaints", "incident_zip": "ZIP Code", "borough": "Borough"},
                color_discrete_sequence=[
                    PALETTE["primary"], PALETTE["secondary"], PALETTE["accent_orange"],
                    PALETTE["accent_green"], PALETTE["accent_purple"]
                ]
            )
            fig_z.update_layout(
                **CHART_LAYOUT_DEFAULTS,
                xaxis=dict(showgrid=True, gridcolor=PALETTE["grid_color"]),
                yaxis=dict(type="category"),
                height=380
            )
            fig_z.update_traces(
                hovertemplate="<b>ZIP: %{y}</b><br>Borough: %{data.name}<br>Volume: %{x:,}<extra></extra>"
            )
            st.plotly_chart(fig_z, use_container_width=True)

    with tab_map:
        if cluster_df is None or cluster_df.empty:
            st.info("No geospatial coordinate data available for current selection.")
        else:
            # Render OpenStreetMap scatter map without external API key
            plot_map = cluster_df.dropna(subset=["lat", "lon"]).copy()
            if plot_map.empty:
                st.info("No geospatial coordinate data available for current selection.")
            else:
                plot_map["count"] = pd.to_numeric(plot_map.get("count"), errors="coerce").fillna(1)
                # Plotly 6.0+ renamed scatter_mapbox -> scatter_map (map_style replaces mapbox_style)
                if hasattr(px, "scatter_map"):
                    fig_m = px.scatter_map(
                        plot_map,
                        lat="lat",
                        lon="lon",
                        size="count",
                        color="borough",
                        hover_name="borough",
                        hover_data={"count": True, "lat": ":.3f", "lon": ":.3f"},
                        zoom=9.8,
                        center={"lat": 40.7128, "lon": -74.0060},
                        map_style="open-street-map",
                        title="<b>NYC Incident Density Clusters (Aggregated Coordinates)</b>",
                        color_discrete_sequence=[
                            PALETTE["primary"], PALETTE["secondary"], PALETTE["accent_orange"],
                            PALETTE["accent_green"], PALETTE["accent_red"]
                        ]
                    )
                else:
                    fig_m = px.scatter_mapbox(
                        plot_map,
                        lat="lat",
                        lon="lon",
                        size="count",
                        color="borough",
                        hover_name="borough",
                        hover_data={"count": True, "lat": ":.3f", "lon": ":.3f"},
                        zoom=9.8,
                        center={"lat": 40.7128, "lon": -74.0060},
                        mapbox_style="open-street-map",
                        title="<b>NYC Incident Density Clusters (Aggregated Coordinates)</b>",
                        color_discrete_sequence=[
                            PALETTE["primary"], PALETTE["secondary"], PALETTE["accent_orange"],
                            PALETTE["accent_green"], PALETTE["accent_red"]
                        ]
                    )
                layout_map = dict(CHART_LAYOUT_DEFAULTS)
                layout_map["margin"] = dict(l=10, r=10, t=40, b=10)
                layout_map["height"] = 450
                fig_m.update_layout(**layout_map)
                st.plotly_chart(fig_m, use_container_width=True)


def render_operational_channels_chart(channel_df: pd.DataFrame, weekday_df: pd.DataFrame) -> None:
    """
    Render operational breakdown:
    - Donut chart of submission channels (Online, Phone, Mobile, Unknown)
    - Grouped Bar chart of Weekday vs Weekend volume and resolution time
    """
    col1, col2 = st.columns(2)

    with col1:
        if channel_df.empty:
            st.info("No channel distribution data available.")
        else:
            fig_c = px.pie(
                channel_df,
                names="channel",
                values="total",
                hole=0.45,
                title="<b>Submission Channel Distribution</b>",
                color="channel",
                color_discrete_sequence=[
                    PALETTE["primary"], PALETTE["secondary"],
                    PALETTE["accent_orange"], PALETTE["accent_green"]
                ]
            )
            fig_c.update_traces(
                textposition="inside",
                textinfo="percent+label",
                hovertemplate="<b>%{label}</b><br>Volume: %{value:,}<br>Share: %{percent}<extra></extra>"
            )
            fig_c.update_layout(
                **CHART_LAYOUT_DEFAULTS,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
                height=360
            )
            st.plotly_chart(fig_c, use_container_width=True)

    with col2:
        if weekday_df.empty:
            st.info("No weekday/weekend operational data available.")
        else:
            fig_w = make_subplots(specs=[[{"secondary_y": True}]])

            fig_w.add_trace(
                go.Bar(
                    x=weekday_df["day_type"],
                    y=weekday_df["total"],
                    name="Volume",
                    marker_color=PALETTE["secondary"],
                    hovertemplate="<b>%{x}</b><br>Volume: %{y:,}<extra></extra>"
                ),
                secondary_y=False
            )

            fig_w.add_trace(
                go.Scatter(
                    x=weekday_df["day_type"],
                    y=weekday_df["avg_resolution_hours"],
                    name="Avg Resolution (Hrs)",
                    mode="lines+markers",
                    line=dict(color=PALETTE["accent_orange"], width=3),
                    marker=dict(size=8, color=PALETTE["accent_orange"]),
                    hovertemplate="<b>%{x}</b><br>Avg Resolution: %{y:.1f} hrs<extra></extra>"
                ),
                secondary_y=True
            )

            fig_w.update_layout(
                **CHART_LAYOUT_DEFAULTS,
                title="<b>Weekday vs. Weekend Operational Dynamics</b>",
                xaxis=dict(showgrid=False),
                yaxis=dict(title="Total Complaints", showgrid=True, gridcolor=PALETTE["grid_color"]),
                yaxis2=dict(title="Avg Resolution (Hours)", showgrid=False, rangemode="tozero"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=360
            )
            st.plotly_chart(fig_w, use_container_width=True)
