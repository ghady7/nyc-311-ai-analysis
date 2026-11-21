"""
AI Copilot Interactive Chat Interface for NYC 311 Analytics.
Integrates Gemini 2.5 Flash Text-to-SQL, AST security guardrails,
collapsible SQL inspection, CSV export, and dynamic Plotly auto-visualizations.
"""

import os
from typing import Optional, List, Tuple
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from services.chatbot_service import (
    ask_copilot,
    STARTER_QUESTIONS
)

# Unified Design System Color Tokens (Apple Frosted Glass & Vibrant Ocean Palette)
PALETTE = {
    "primary": "#0A84FF",         # Apple System Blue
    "primary_light": "#64D2FF",   # Apple Cyan
    "secondary": "#5E5CE6",       # Apple Indigo
    "accent_orange": "#FF9F0A",   # Apple Amber
    "accent_green": "#30D158",    # Apple Mint
    "accent_purple": "#BF5AF2",   # Apple Violet
    "surface_card": "rgba(14, 25, 48, 0.70)",
    "slate_900": "#080E1E",       # Apple Midnight
    "slate_700": "rgba(255, 255, 255, 0.18)",
    "slate_500": "#98989D",       # Apple Muted Axis Labels
    "slate_200": "#E5E5EA",       # Apple Primary Axis Labels
    "slate_100": "#F5F5F7",       # Pure Apple Title Text
    "grid_color": "rgba(255, 255, 255, 0.07)"
}

CHAT_PLOTLY_CONFIG = {
    "displayModeBar": "hover",
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]
}


def _classify_chat_columns(df: pd.DataFrame) -> Tuple[List[str], List[str], List[str]]:
    """Identify date, categorical, and numeric metric columns in result DataFrame."""
    date_cols = []
    cat_cols = []
    num_cols = []

    for col in df.columns:
        col_lower = str(col).lower()
        if any(term in col_lower for term in ("date", "time", "day", "month", "year")):
            date_cols.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            if not any(pat in col_lower for pat in ("_key", "_id", "unique_key", "zip")):
                num_cols.append(col)
        else:
            cat_cols.append(col)

    return date_cols, cat_cols, num_cols


def render_chat_visualization(df: pd.DataFrame, key_prefix: str = "chat") -> None:
    """
    Automatically detect the shape of query results and generate the optimal
    interactive Plotly chart (Metric Cards, Bar Chart, Line Chart, or Area Chart).
    """
    if df.empty:
        st.info("Query returned 0 rows.")
        return

    # Case 1: Single-row aggregate result (e.g. Total count or average)
    if len(df) == 1:
        cols = st.columns(min(len(df.columns), 4), gap="medium")
        for idx, col_name in enumerate(df.columns):
            val = df[col_name].iloc[0]
            if pd.isna(val) or val is None:
                val_str = "N/A"
            elif isinstance(val, (int, float)):
                val_str = f"{val:,.2f}" if isinstance(val, float) else f"{val:,}"
            else:
                val_str = str(val)
            label = str(col_name).replace("_", " ").title()
            with cols[idx % len(cols)]:
                st.metric(label=label, value=val_str)
        return

    date_cols, cat_cols, num_cols = _classify_chat_columns(df)

    # If no numeric metrics to plot, render table directly
    if not num_cols:
        st.dataframe(df, use_container_width=True, hide_index=True)
        return

    metric_col = num_cols[0]
    metric_label = str(metric_col).replace("_", " ").title()

    # Determine default chart type
    if date_cols:
        x_col = date_cols[0]
        default_chart = "Line Chart"
    elif cat_cols:
        x_col = cat_cols[0]
        default_chart = "Bar Chart"
    else:
        x_col = df.columns[0]
        default_chart = "Bar Chart"

    x_label = str(x_col).replace("_", " ").title()

    # Visual Format Selector
    col_type, _ = st.columns([2, 5])
    with col_type:
        chart_choice = st.selectbox(
            "Visual Format",
            options=["Bar Chart", "Line Chart", "Area Chart"],
            index=["Bar Chart", "Line Chart", "Area Chart"].index(default_chart),
            key=f"chart_type_{key_prefix}",
            label_visibility="collapsed"
        )

    layout_args = dict(
        font=dict(family="-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Plus Jakarta Sans', sans-serif", size=11.5, color=PALETTE["slate_500"]),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=36, r=24, t=28, b=36),
        xaxis=dict(
            showgrid=True,
            gridcolor=PALETTE["grid_color"],
            zeroline=False,
            tickfont=dict(size=10.5, color=PALETTE["slate_500"]),
            automargin=True
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=PALETTE["grid_color"],
            zeroline=False,
            tickfont=dict(size=10.5, color=PALETTE["slate_200"]),
            automargin=True
        ),
        hoverlabel=dict(
            bgcolor="rgba(8, 16, 34, 0.94)",
            font_size=12,
            font_family="-apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif",
            font_color=PALETTE["slate_100"],
            bordercolor="rgba(100, 210, 255, 0.35)"
        )
    )

    if chart_choice == "Bar Chart":
        plot_df = df.head(25).copy()
        fig = px.bar(
            plot_df,
            x=metric_col,
            y=x_col,
            orientation="h",
            color_discrete_sequence=[PALETTE["primary"]],
            labels={metric_col: metric_label, x_col: x_label}
        )
        fig.update_layout(
            **layout_args,
            bargap=0.28,
            height=max(270, min(520, len(plot_df) * 30))
        )
        fig.update_yaxes(showgrid=False)
        fig.update_xaxes(separatethousands=True)
        fig.update_traces(
            marker=dict(line=dict(color=PALETTE["primary_light"], width=0.8)),
            hovertemplate="<b>%{y}</b>: <b>%{x:,}</b><extra></extra>"
        )
        st.plotly_chart(fig, use_container_width=True, config=CHAT_PLOTLY_CONFIG)

    elif chart_choice == "Line Chart":
        fig = px.line(
            df,
            x=x_col,
            y=metric_col,
            markers=True,
            color_discrete_sequence=[PALETTE["secondary"]],
            labels={metric_col: metric_label, x_col: x_label}
        )
        fig.update_layout(**layout_args, height=360)
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(separatethousands=True)
        fig.update_traces(
            line=dict(width=2.6, shape="spline"),
            marker=dict(size=6, line=dict(color=PALETTE["surface_card"], width=1.2)),
            hovertemplate="<b>%{x}</b>: <b>%{y:,}</b><extra></extra>"
        )
        st.plotly_chart(fig, use_container_width=True, config=CHAT_PLOTLY_CONFIG)

    elif chart_choice == "Area Chart":
        fig = px.area(
            df,
            x=x_col,
            y=metric_col,
            color_discrete_sequence=[PALETTE["accent_orange"]],
            labels={metric_col: metric_label, x_col: x_label}
        )
        fig.update_layout(**layout_args, height=360)
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(separatethousands=True)
        fig.update_traces(
            line=dict(width=2.4),
            hovertemplate="<b>%{x}</b>: <b>%{y:,}</b><extra></extra>"
        )
        st.plotly_chart(fig, use_container_width=True, config=CHAT_PLOTLY_CONFIG)


def render_copilot_chat() -> None:
    """
    Main Copilot Chat interface component:
    - Interactive starter question buttons
    - Chat turn history with SQL inspection, auto-visualization, and CSV download
    - Real-time natural language query execution with AST safety
    """
    with st.container(border=True):
        st.caption("NATURAL LANGUAGE SQL INTERFACE · GEMINI 2.5 FLASH")
        st.subheader("AI Data Analyst Copilot")
        st.caption(
            "Inquire in plain language. Queries are parsed and translated to SQL against the PostgreSQL Star Schema warehouse, audited by triple-layer AST guardrails, and visualized dynamically."
        )

    # Initialize chat message history
    if "copilot_messages" not in st.session_state:
        st.session_state.copilot_messages = []

    # API Key Configuration
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        with st.container(border=True):
            user_key = st.text_input(
                "Gemini API Key Required",
                type="password",
                help="Enter your Google AI Studio API key. It remains session-isolated.",
                key="user_entered_gemini_key"
            )
            if user_key:
                api_key = user_key
                st.session_state["session_gemini_key"] = user_key
            else:
                api_key = st.session_state.get("session_gemini_key")

    # Clickable Starter Questions
    with st.container(border=True):
        st.caption("SUGGESTED ANALYTICAL INQUIRIES")
        clicked_question: Optional[str] = None
        cols = st.columns(2, gap="small")
        for idx, q_text in enumerate(STARTER_QUESTIONS):
            with cols[idx % 2]:
                if st.button(q_text, key=f"starter_q_{idx}", use_container_width=True):
                    clicked_question = q_text

    # Render previous conversation history
    for i, msg in enumerate(st.session_state.copilot_messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("guarded_sql"):
                with st.expander("Inspect Verified SQL Query"):
                    st.code(msg["guarded_sql"], language="sql")
            df = msg.get("df")
            if df is not None and not df.empty:
                tab_viz, tab_data = st.tabs(["Visualization", "Data Table"])
                with tab_viz:
                    render_chat_visualization(df, key_prefix=f"history_{i}")
                with tab_data:
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    csv_bytes = df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label="Download CSV Dataset",
                        data=csv_bytes,
                        file_name=f"nyc311_query_result_{i}.csv",
                        mime="text/csv",
                        key=f"dl_history_{i}"
                    )

    # Input Box handling
    chat_prompt = st.chat_input("Ask an analytical question (e.g. 'Show top 5 noise complaints by borough')...")
    active_prompt = clicked_question or chat_prompt

    if active_prompt:
        if not api_key:
            st.warning("Please configure your GEMINI_API_KEY above to enable Text-to-SQL translation.")
            return

        # 1. Display user query
        st.session_state.copilot_messages.append({"role": "user", "content": active_prompt})
        with st.chat_message("user"):
            st.markdown(active_prompt)

        # 2. Process query via Assistant
        with st.chat_message("assistant"):
            with st.spinner("Analyzing schema, generating SQL, and applying security guardrails..."):
                result = ask_copilot(active_prompt, api_key=api_key)

                if result["success"]:
                    st.markdown(result["summary"])
                    if result["guarded_sql"]:
                        with st.expander("Inspect Verified SQL Query"):
                            st.code(result["guarded_sql"], language="sql")

                    df = result["df"]
                    current_idx = len(st.session_state.copilot_messages)
                    if not df.empty:
                        tab_viz, tab_data = st.tabs(["Visualization", "Data Table"])
                        with tab_viz:
                            render_chat_visualization(df, key_prefix=f"live_{current_idx}")
                        with tab_data:
                            st.dataframe(df, use_container_width=True, hide_index=True)
                            csv_bytes = df.to_csv(index=False).encode("utf-8")
                            st.download_button(
                                label="Download CSV Dataset",
                                data=csv_bytes,
                                file_name=f"nyc311_query_result_{current_idx}.csv",
                                mime="text/csv",
                                key=f"dl_live_{current_idx}"
                            )

                    st.session_state.copilot_messages.append({
                        "role": "assistant",
                        "content": result["summary"],
                        "guarded_sql": result["guarded_sql"],
                        "df": df
                    })
                else:
                    st.error(result["summary"])
                    st.session_state.copilot_messages.append({
                        "role": "assistant",
                        "content": result["summary"],
                        "guarded_sql": None,
                        "df": pd.DataFrame()
                    })