"""
Interactive Plotly Visual Analytics Charts for NYC 311 Dashboard.
Implements executive-styled visualizations with dark enterprise theme:
- Volume Trend with 7-Day Rolling Average (Combo Bar + Spline Line)
- Top Complaint Categories & Types (Horizontal Bar with Category Colors)
- Agency Performance Matrix (Bubble Scatter with Multi-Dimensional Hover)
- Geographic Breakdown by Borough & Top Zip Codes + Carto-Darkmatter Geospatial Map
- Operational Channels & Weekday/Weekend Breakdown (Donut + Dual-Axis Grouped Bar)
"""

from typing import Dict, Any, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# Unified Design System Color Tokens (Apple Frosted Glass & Vibrant Ocean Palette)
PALETTE = {
    "primary": "#0A84FF",         # Apple System Blue
    "primary_light": "#64D2FF",   # Apple Cyan / Ice Blue
    "secondary": "#5E5CE6",       # Apple Indigo
    "accent_orange": "#FF9F0A",   # Apple Amber
    "accent_green": "#30D158",    # Apple Mint / Emerald
    "accent_red": "#FF453A",      # Apple Coral / Rose
    "accent_purple": "#BF5AF2",   # Apple Violet
    "surface_card": "rgba(14, 25, 48, 0.70)", # Frosted Mirror Glass Surface
    "slate_900": "#080E1E",       # Apple Midnight
    "slate_700": "rgba(255, 255, 255, 0.18)",
    "slate_500": "#98989D",       # Apple Muted Axis Labels
    "slate_200": "#E5E5EA",       # Apple Primary Axis Labels
    "slate_100": "#F5F5F7",       # Pure Apple Title Text
    "grid_color": "rgba(255, 255, 255, 0.07)",
    "zero_line": "rgba(255, 255, 255, 0.16)"
}

PLOTLY_CONFIG = {
    "displayModeBar": "hover",
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]
}

CHART_LAYOUT_DEFAULTS = dict(
    font=dict(
        family="-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Plus Jakarta Sans', sans-serif",
        size=11.5,
        color=PALETTE["slate_500"]
    ),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=44, r=24, t=58, b=40),
    hovermode="closest",
    hoverlabel=dict(
        bgcolor="rgba(8, 16, 34, 0.94)",
        font_size=12,
        font_family="-apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif",
        font_color=PALETTE["slate_100"],
        bordercolor="rgba(100, 210, 255, 0.35)"
    )
)


def render_volume_trend_chart(df: pd.DataFrame) -> None:
    """
    Render daily complaint volume combo chart:
    - Translucent bar chart for daily volume
    - Smooth amber spline line for 7-day rolling average
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
            marker=dict(
                color="rgba(10, 132, 255, 0.75)",
                line=dict(color="rgba(100, 210, 255, 0.85)", width=1)
            ),
            hovertemplate="<b>%{x|%b %d, %Y}</b><br>Daily Volume: <b>%{y:,}</b><extra></extra>"
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
                line=dict(color=PALETTE["accent_orange"], width=2.8, shape="spline"),
                marker=dict(
                    size=5.5,
                    color=PALETTE["accent_orange"],
                    line=dict(color=PALETTE["surface_card"], width=1.2)
                ),
                hovertemplate="<b>%{x|%b %d, %Y}</b><br>7-Day Moving Avg: <b>%{y:,.1f}</b><extra></extra>"
            )
        )

    layout_trend = dict(CHART_LAYOUT_DEFAULTS)
    layout_trend["hovermode"] = "x unified"

    fig.update_layout(
        **layout_trend,
        bargap=0.28,
        title=dict(
            text="<b>Daily Incident Ingestion & 7-Day Moving Trend</b>",
            font=dict(family="Plus Jakarta Sans, sans-serif", size=14, color=PALETTE["slate_100"]),
            x=0.0,
            xanchor="left",
            y=0.96
        ),
        xaxis=dict(
            title="",
            showgrid=False,
            linecolor=PALETTE["zero_line"],
            tickformat="%b %d",
            tickfont=dict(size=10.5, color=PALETTE["slate_500"]),
            automargin=True
        ),
        yaxis=dict(
            title=dict(text="Service Requests", font=dict(size=11, color=PALETTE["slate_500"])),
            showgrid=True,
            gridcolor=PALETTE["grid_color"],
            zeroline=True,
            zerolinecolor=PALETTE["zero_line"],
            rangemode="tozero",
            tickfont=dict(size=10.5, color=PALETTE["slate_500"]),
            separatethousands=True
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.03,
            xanchor="right",
            x=1.0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color=PALETTE["slate_200"])
        ),
        height=370
    )

    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)


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
        labels={"complaint_count": "Service Requests", "complaint_type": "", "complaint_category": "Category"},
        color_discrete_sequence=[
            PALETTE["primary"], PALETTE["secondary"], PALETTE["accent_orange"],
            PALETTE["accent_green"], PALETTE["accent_purple"], PALETTE["accent_red"]
        ]
    )

    layout_cfg = dict(CHART_LAYOUT_DEFAULTS)
    layout_cfg["margin"] = dict(l=10, r=20, t=36, b=36)

    fig.update_layout(
        **layout_cfg,
        bargap=0.22,
        showlegend=False,
        title=dict(
            text="<b>Top Municipal Complaint Types</b>",
            font=dict(family="Plus Jakarta Sans, sans-serif", size=13.5, color=PALETTE["slate_100"]),
            x=0.0,
            xanchor="left",
            y=0.98
        ),
        xaxis=dict(
            title=dict(text="Service Requests", font=dict(size=11, color=PALETTE["slate_500"])),
            showgrid=True,
            gridcolor=PALETTE["grid_color"],
            zeroline=False,
            tickfont=dict(size=10.5, color=PALETTE["slate_500"]),
            separatethousands=True
        ),
        yaxis=dict(
            showgrid=False,
            tickfont=dict(size=11, family="Plus Jakarta Sans, sans-serif", color=PALETTE["slate_200"]),
            automargin=True
        ),
        height=420
    )
    fig.update_traces(
        marker=dict(line=dict(color="rgba(255,255,255,0.08)", width=0.5)),
        hovertemplate="<b>%{y}</b><br>Category: <b>%{data.name}</b><br>Volume: <b>%{x:,}</b><extra></extra>"
    )

    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)


def render_agency_performance_matrix(df: pd.DataFrame) -> None:
    """
    Render Agency Performance Matrix with Dual Modes:
    1. Ranked Comparison (Horizontal bar of agencies by volume & resolution rate)
    2. Operational Efficiency Matrix (Scatter plot of volume vs. resolution rate %)
    """
    if df.empty:
        st.info("No agency performance records available for current filter selection.")
        return

    plot_df = df.copy()
    plot_df["avg_resolution_hours"] = pd.to_numeric(plot_df.get("avg_resolution_hours"), errors="coerce").fillna(0.0)
    plot_df["closure_rate"] = pd.to_numeric(plot_df.get("closure_rate"), errors="coerce").fillna(0.0)
    plot_df["total_complaints"] = pd.to_numeric(plot_df.get("total_complaints"), errors="coerce").fillna(0).astype(int)
    plot_df["agency_name"] = plot_df.get("agency_name", "").fillna("Unknown")
    plot_df["agency_code"] = plot_df.get("agency_code", "").fillna("N/A")
    plot_df["bubble_size"] = plot_df["avg_resolution_hours"].clip(lower=6.0, upper=36.0)

    # Filter out agencies with 0 volume
    plot_df = plot_df[plot_df["total_complaints"] > 0].copy()
    if plot_df.empty:
        st.info("No active agency records available.")
        return

    # Semantic color gradient (emerald for high closure rate, amber for medium, rose for low)
    semantic_scale = [
        [0.0, PALETTE["accent_red"]],
        [0.40, PALETTE["accent_orange"]],
        [0.70, PALETTE["secondary"]],
        [1.0, PALETTE["accent_green"]]
    ]

    tab_rank, tab_scatter = st.tabs(["Agency Performance Ranking", "Resolution Efficiency Matrix"])

    with tab_rank:
        rank_df = plot_df.sort_values(by="total_complaints", ascending=True)
        fig_rank = px.bar(
            rank_df,
            x="total_complaints",
            y="agency_code",
            color="closure_rate",
            orientation="h",
            color_continuous_scale=semantic_scale,
            labels={
                "total_complaints": "Total Requests",
                "agency_code": "Agency",
                "closure_rate": "Resolution Rate (%)"
            }
        )

        layout_rank = dict(CHART_LAYOUT_DEFAULTS)
        layout_rank["margin"] = dict(l=10, r=20, t=28, b=36)

        fig_rank.update_layout(
            **layout_rank,
            bargap=0.22,
            xaxis=dict(
                title=dict(text="Total Service Requests", font=dict(size=11, color=PALETTE["slate_500"])),
                showgrid=True,
                gridcolor=PALETTE["grid_color"],
                zeroline=False,
                tickfont=dict(size=10.5, color=PALETTE["slate_500"]),
                separatethousands=True
            ),
            yaxis=dict(
                showgrid=False,
                tickfont=dict(size=11, family="Plus Jakarta Sans, sans-serif", color=PALETTE["slate_200"]),
                automargin=True
            ),
            coloraxis_colorbar=dict(
                title=dict(text="Resolution %", font=dict(size=10.5, color=PALETTE["slate_200"])),
                thickness=10,
                len=0.72,
                outlinewidth=0,
                ticksuffix="%",
                tickfont=dict(size=10, color=PALETTE["slate_500"])
            ),
            height=370
        )
        fig_rank.update_traces(
            hovertemplate=(
                "<b>%{customdata[0]}</b> (%{y})<br>"
                "Total Ingested: <b>%{x:,}</b><br>"
                "Resolution Rate: <b>%{customdata[1]:.1f}%</b><br>"
                "Avg Resolution Duration: <b>%{customdata[2]:.1f} hrs</b><extra></extra>"
            ),
            customdata=rank_df[["agency_name", "closure_rate", "avg_resolution_hours"]].values
        )
        st.plotly_chart(fig_rank, use_container_width=True, config=PLOTLY_CONFIG)

    with tab_scatter:
        # Scatter plot using REAL closure_rate (0% to 100%) instead of 0% SLA
        scatter_df = plot_df.copy()
        scatter_df["display_label"] = scatter_df.apply(
            lambda r: r["agency_code"] if r["total_complaints"] >= 1500 else "",
            axis=1
        )

        fig_scatter = px.scatter(
            scatter_df,
            x="total_complaints",
            y="closure_rate",
            size="bubble_size",
            color="avg_resolution_hours",
            text="display_label",
            labels={
                "total_complaints": "Ticket Volume",
                "closure_rate": "Resolution Rate (%)",
                "avg_resolution_hours": "Avg Hrs"
            },
            color_continuous_scale="Viridis_r",
            size_max=32
        )

        fig_scatter.update_traces(
            textposition="top center",
            textfont=dict(family="Plus Jakarta Sans, sans-serif", size=10.5, weight="bold", color=PALETTE["slate_100"]),
            marker=dict(
                opacity=0.88,
                line=dict(color="rgba(15, 23, 42, 0.85)", width=1.2)
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b> (%{customdata[3]})<br>"
                "Total Ingested: <b>%{x:,}</b><br>"
                "Resolution Rate: <b>%{y:.1f}%</b><br>"
                "Avg Resolution: <b>%{customdata[2]:.1f} hrs</b><extra></extra>"
            ),
            customdata=scatter_df[["agency_name", "closure_rate", "avg_resolution_hours", "agency_code"]].values
        )

        # Add Resolution Benchmark Reference Line at 80%
        fig_scatter.add_hline(
            y=80,
            line_dash="dot",
            line_color=PALETTE["accent_green"],
            line_width=1.5,
            annotation_text="Target Benchmark (80%)",
            annotation_position="bottom right",
            annotation_font=dict(size=10, color=PALETTE["accent_green"])
        )

        layout_scatter = dict(CHART_LAYOUT_DEFAULTS)
        layout_scatter["margin"] = dict(l=44, r=20, t=28, b=36)

        fig_scatter.update_layout(
            **layout_scatter,
            xaxis=dict(
                title=dict(text="Ticket Volume", font=dict(size=11, color=PALETTE["slate_500"])),
                showgrid=True,
                gridcolor=PALETTE["grid_color"],
                zeroline=False,
                tickfont=dict(size=10.5, color=PALETTE["slate_500"]),
                separatethousands=True
            ),
            yaxis=dict(
                title=dict(text="Resolution Rate (%)", font=dict(size=11, color=PALETTE["slate_500"])),
                showgrid=True,
                gridcolor=PALETTE["grid_color"],
                zeroline=False,
                range=[-5, 110],
                ticksuffix="%",
                tickfont=dict(size=10.5, color=PALETTE["slate_500"])
            ),
            coloraxis_colorbar=dict(
                title=dict(text="Avg Hrs", font=dict(size=10.5, color=PALETTE["slate_200"])),
                thickness=10,
                len=0.72,
                outlinewidth=0,
                tickfont=dict(size=10, color=PALETTE["slate_500"])
            ),
            height=370
        )
        st.plotly_chart(fig_scatter, use_container_width=True, config=PLOTLY_CONFIG)


def render_geographic_charts(
    borough_df: pd.DataFrame,
    zip_df: pd.DataFrame,
    cluster_df: Optional[pd.DataFrame] = None
) -> None:
    """
    Render Geographic breakdown:
    - Tab 1: Borough volume & avg resolution hours
    - Tab 2: Top 10 Incident Zip Codes
    - Tab 3: Geospatial Density Map (Carto-Darkmatter / OpenStreetMap)
    """
    tab_borough, tab_zip, tab_map = st.tabs([
        "Borough Comparison",
        "Top Incident Zip Codes",
        "Geospatial Density Map"
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
                    marker=dict(
                        color="rgba(10, 132, 255, 0.78)",
                        line=dict(color="rgba(100, 210, 255, 0.85)", width=1)
                    ),
                    hovertemplate="<b>%{x}</b><br>Volume: <b>%{y:,}</b><extra></extra>"
                ),
                secondary_y=False
            )

            fig_b.add_trace(
                go.Scatter(
                    x=borough_df["borough"],
                    y=borough_df["avg_resolution_hours"],
                    name="Avg Resolution (Hrs)",
                    mode="lines+markers",
                    line=dict(color=PALETTE["accent_orange"], width=2.8),
                    marker=dict(
                        size=8,
                        color=PALETTE["accent_orange"],
                        line=dict(color=PALETTE["surface_card"], width=1.5)
                    ),
                    hovertemplate="<b>%{x}</b><br>Avg Resolution: <b>%{y:.1f} hrs</b><extra></extra>"
                ),
                secondary_y=True
            )

            fig_b.update_layout(
                **CHART_LAYOUT_DEFAULTS,
                bargap=0.38,
                title=dict(
                    text="<b>Complaint Volume & Average Resolution Time by Borough</b>",
                    font=dict(family="Plus Jakarta Sans, sans-serif", size=14, color=PALETTE["slate_100"]),
                    x=0.0,
                    xanchor="left",
                    y=0.96
                ),
                xaxis=dict(
                    showgrid=False,
                    linecolor=PALETTE["zero_line"],
                    tickfont=dict(size=11, color=PALETTE["slate_200"])
                ),
                yaxis=dict(
                    title=dict(text="Complaints", font=dict(size=11, color=PALETTE["slate_500"])),
                    showgrid=True,
                    gridcolor=PALETTE["grid_color"],
                    zeroline=False,
                    tickfont=dict(size=10.5, color=PALETTE["slate_500"]),
                    separatethousands=True
                ),
                yaxis2=dict(
                    title=dict(text="Avg Resolution (Hours)", font=dict(size=11, color=PALETTE["accent_orange"])),
                    showgrid=False,
                    zeroline=False,
                    rangemode="tozero",
                    tickfont=dict(size=10.5, color=PALETTE["slate_500"])
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.03,
                    xanchor="right",
                    x=1.0,
                    bgcolor="rgba(0,0,0,0)",
                    font=dict(size=11, color=PALETTE["slate_200"])
                ),
                height=390
            )

            st.plotly_chart(fig_b, use_container_width=True, config=PLOTLY_CONFIG)

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
                bargap=0.28,
                title=dict(
                    text="<b>Top 10 Incident Zip Codes by Volume</b>",
                    font=dict(family="Plus Jakarta Sans, sans-serif", size=14, color=PALETTE["slate_100"]),
                    x=0.0,
                    xanchor="left",
                    y=0.96
                ),
                xaxis=dict(
                    title=dict(text="Complaints", font=dict(size=11, color=PALETTE["slate_500"])),
                    showgrid=True,
                    gridcolor=PALETTE["grid_color"],
                    zeroline=False,
                    tickfont=dict(size=10.5, color=PALETTE["slate_500"]),
                    separatethousands=True
                ),
                yaxis=dict(
                    type="category",
                    title=dict(text="ZIP Code", font=dict(size=11, color=PALETTE["slate_500"])),
                    tickfont=dict(size=11, color=PALETTE["slate_200"]),
                    automargin=True
                ),
                legend=dict(
                    title=dict(text=""),
                    orientation="h",
                    yanchor="top",
                    y=-0.14,
                    xanchor="center",
                    x=0.5,
                    bgcolor="rgba(0,0,0,0)",
                    font=dict(size=10.5, color=PALETTE["slate_200"])
                ),
                height=410
            )
            fig_z.update_traces(
                marker=dict(line=dict(color="rgba(255,255,255,0.08)", width=0.5)),
                hovertemplate="<b>ZIP: %{y}</b><br>Borough: %{data.name}<br>Volume: <b>%{x:,}</b><extra></extra>"
            )
            st.plotly_chart(fig_z, use_container_width=True, config=PLOTLY_CONFIG)

    with tab_map:
        if cluster_df is None or cluster_df.empty:
            st.info("No geospatial coordinate data available for current selection.")
        else:
            plot_map = cluster_df.dropna(subset=["lat", "lon"]).copy()
            if plot_map.empty:
                st.info("No geospatial coordinate data available for current selection.")
            else:
                plot_map["count"] = pd.to_numeric(plot_map.get("count"), errors="coerce").fillna(1)
                map_args = dict(
                    lat="lat",
                    lon="lon",
                    size="count",
                    color="borough",
                    hover_name="borough",
                    hover_data={"count": True, "lat": ":.3f", "lon": ":.3f"},
                    zoom=9.8,
                    center={"lat": 40.7128, "lon": -74.0060},
                    title="<b>NYC Incident Geospatial Density Clusters</b>",
                    color_discrete_sequence=[
                        PALETTE["primary_light"], PALETTE["secondary"], PALETTE["accent_orange"],
                        PALETTE["accent_green"], PALETTE["accent_red"]
                    ]
                )

                if hasattr(px, "scatter_map"):
                    fig_m = px.scatter_map(plot_map, map_style="carto-darkmatter", **map_args)
                else:
                    fig_m = px.scatter_mapbox(plot_map, mapbox_style="carto-darkmatter", **map_args)

                layout_map = dict(CHART_LAYOUT_DEFAULTS)
                layout_map["margin"] = dict(l=8, r=8, t=52, b=8)
                layout_map["height"] = 480
                layout_map["title"] = dict(
                    text="<b>NYC Incident Geospatial Density Clusters</b>",
                    font=dict(family="Plus Jakarta Sans, sans-serif", size=14, color=PALETTE["slate_100"]),
                    x=0.01,
                    xanchor="left",
                    y=0.97
                )
                layout_map["legend"] = dict(
                    title=dict(text=""),
                    orientation="h",
                    yanchor="bottom",
                    y=1.01,
                    xanchor="right",
                    x=0.99,
                    bgcolor="rgba(0,0,0,0)",
                    font=dict(size=11, color=PALETTE["slate_200"])
                )
                fig_m.update_layout(**layout_map)
                st.plotly_chart(fig_m, use_container_width=True, config=PLOTLY_CONFIG)


def render_operational_channels_chart(channel_df: pd.DataFrame, weekday_df: pd.DataFrame) -> None:
    """
    Render operational breakdown:
    - Donut chart of submission channels (Online, Phone, Mobile, Unknown)
    - Grouped Bar chart of Weekday vs Weekend volume and resolution time
    """
    col1, col2 = st.columns(2, gap="medium")

    with col1:
        if channel_df.empty:
            st.info("No channel distribution data available.")
        else:
            fig_c = px.pie(
                channel_df,
                names="channel",
                values="total",
                hole=0.60,
                title="<b>Submission Channel Distribution</b>",
                color="channel",
                color_discrete_sequence=[
                    PALETTE["primary"], PALETTE["secondary"],
                    PALETTE["accent_orange"], PALETTE["accent_green"],
                    PALETTE["accent_purple"]
                ]
            )
            fig_c.update_traces(
                textposition="inside",
                textinfo="percent",
                insidetextorientation="horizontal",
                marker=dict(line=dict(color=PALETTE["surface_card"], width=2)),
                textfont=dict(family="Plus Jakarta Sans, sans-serif", size=11.5, color="#FFFFFF"),
                hovertemplate="<b>%{label}</b><br>Volume: <b>%{value:,}</b><br>Share: <b>%{percent}</b><extra></extra>"
            )
            layout_donut = dict(CHART_LAYOUT_DEFAULTS)
            layout_donut["margin"] = dict(l=20, r=20, t=54, b=48)
            fig_c.update_layout(
                **layout_donut,
                title=dict(
                    text="<b>Civic Intake Channel Distribution</b>",
                    font=dict(family="Plus Jakarta Sans, sans-serif", size=14, color=PALETTE["slate_100"]),
                    x=0.0,
                    xanchor="left",
                    y=0.96
                ),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.04,
                    xanchor="center",
                    x=0.5,
                    bgcolor="rgba(0,0,0,0)",
                    font=dict(size=11, color=PALETTE["slate_200"])
                ),
                height=370
            )
            st.plotly_chart(fig_c, use_container_width=True, config=PLOTLY_CONFIG)

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
                    marker=dict(
                        color="rgba(100, 210, 255, 0.78)",
                        line=dict(color=PALETTE["primary_light"], width=1)
                    ),
                    hovertemplate="<b>%{x}</b><br>Volume: <b>%{y:,}</b><extra></extra>"
                ),
                secondary_y=False
            )

            fig_w.add_trace(
                go.Scatter(
                    x=weekday_df["day_type"],
                    y=weekday_df["avg_resolution_hours"],
                    name="Avg Resolution (Hrs)",
                    mode="lines+markers",
                    line=dict(color=PALETTE["accent_orange"], width=2.8),
                    marker=dict(
                        size=8.5,
                        color=PALETTE["accent_orange"],
                        line=dict(color=PALETTE["surface_card"], width=1.5)
                    ),
                    hovertemplate="<b>%{x}</b><br>Avg Resolution: <b>%{y:.1f} hrs</b><extra></extra>"
                ),
                secondary_y=True
            )

            fig_w.update_layout(
                **CHART_LAYOUT_DEFAULTS,
                bargap=0.45,
                title=dict(
                    text="<b>Weekday vs. Weekend Operational Dynamics</b>",
                    font=dict(family="Plus Jakarta Sans, sans-serif", size=14, color=PALETTE["slate_100"]),
                    x=0.0,
                    xanchor="left",
                    y=0.96
                ),
                xaxis=dict(
                    showgrid=False,
                    linecolor=PALETTE["zero_line"],
                    tickfont=dict(size=11, color=PALETTE["slate_200"])
                ),
                yaxis=dict(
                    title=dict(text="Complaints", font=dict(size=11, color=PALETTE["slate_500"])),
                    showgrid=True,
                    gridcolor=PALETTE["grid_color"],
                    zeroline=False,
                    tickfont=dict(size=10.5, color=PALETTE["slate_500"]),
                    separatethousands=True
                ),
                yaxis2=dict(
                    title=dict(text="Avg Resolution (Hours)", font=dict(size=11, color=PALETTE["accent_orange"])),
                    showgrid=False,
                    zeroline=False,
                    rangemode="tozero",
                    tickfont=dict(size=10.5, color=PALETTE["slate_500"])
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.03,
                    xanchor="right",
                    x=1.0,
                    bgcolor="rgba(0,0,0,0)",
                    font=dict(size=11, color=PALETTE["slate_200"])
                ),
                height=370
            )
            st.plotly_chart(fig_w, use_container_width=True, config=PLOTLY_CONFIG)