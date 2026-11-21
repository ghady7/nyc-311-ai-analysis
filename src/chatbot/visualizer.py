"""
Automated Data Visualization Engine for NYC 311 Analytics
Intelligently inspects SQL result DataFrames and renders the optimal
interactive chart (Bar, Line, Area, Donut, KPI Card, Map) in Streamlit.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import streamlit as st
import altair as alt


# Non-measurable columns that should NOT be used as metric values
KEY_COLUMN_PATTERNS = {"_key", "_id", "unique_key", "bbl", "zip", "incident_zip"}


def sanitize_df_for_altair(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Sanitize DataFrame column names to prevent Altair / Vega expression errors
    caused by special characters, dots, parentheses, or spaces.
    Returns sanitized copy and mapping of clean_name -> original_name.
    """
    clean_df = df.copy()
    col_mapping = {}
    new_cols = []
    
    for col in clean_df.columns:
        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", str(col))
        if clean_name.startswith("_"):
            clean_name = "col" + clean_name
        # Ensure uniqueness
        base_name = clean_name
        counter = 1
        while clean_name in col_mapping:
            clean_name = f"{base_name}_{counter}"
            counter += 1
            
        col_mapping[clean_name] = str(col)
        new_cols.append(clean_name)
        
    clean_df.columns = new_cols
    return clean_df, col_mapping


def classify_columns(df: pd.DataFrame) -> Tuple[List[str], List[str], List[str]]:
    """
    Classify DataFrame columns into:
    1. Temporal / Date columns
    2. Categorical / Label columns
    3. Measurable numeric metric columns
    """
    temporal_cols = []
    categorical_cols = []
    numeric_cols = []

    for col in df.columns:
        col_lower = str(col).lower()
        
        # Check for temporal columns
        if any(term in col_lower for term in ("date", "time", "year", "month", "day")):
            temporal_cols.append(col)
            continue
            
        # Check for numeric metrics
        if pd.api.types.is_numeric_dtype(df[col]):
            # Filter out technical keys and ID columns
            if not any(pattern in col_lower for pattern in KEY_COLUMN_PATTERNS):
                numeric_cols.append(col)
                continue

        # Everything else is categorical
        categorical_cols.append(col)

    return temporal_cols, categorical_cols, numeric_cols


def render_metric_card(df: pd.DataFrame):
    """Render single-row or scalar aggregate results as prominent KPI cards."""
    if df.empty or len(df.columns) == 0:
        return

    num_cols = min(len(df.columns), 4)
    if num_cols <= 0:
        return
        
    cols = st.columns(num_cols)
    for i, col_name in enumerate(df.columns):
        val = df[col_name].iloc[0]
        
        if pd.isna(val) or val is None:
            formatted = "N/A"
        elif isinstance(val, float):
            formatted = f"{val:,.2f}"
        elif isinstance(val, int):
            formatted = f"{val:,}"
        else:
            formatted = str(val)
            
        clean_label = str(col_name).replace("_", " ").title()
        with cols[i % len(cols)]:
            st.metric(label=clean_label, value=formatted)


def render_bar_chart(df: pd.DataFrame, cat_col: str, num_col: str, orig_cat: str = None, orig_num: str = None):
    """Render styled interactive Altair bar chart."""
    cat_title = (orig_cat or cat_col).replace("_", " ").title()
    num_title = (orig_num or num_col).replace("_", " ").title()

    plot_df = df.head(25).copy()
    plot_df = plot_df.sort_values(by=num_col, ascending=False)
    
    chart = (
        alt.Chart(plot_df)
        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, color="#1F497D")
        .encode(
            y=alt.Y(f"{cat_col}:N", sort="-x", title=cat_title),
            x=alt.X(f"{num_col}:Q", title=num_title),
            tooltip=[
                alt.Tooltip(f"{cat_col}:N", title=cat_title),
                alt.Tooltip(f"{num_col}:Q", title=num_title, format=",.2f")
            ]
        )
        .properties(height=max(250, min(600, len(plot_df) * 32)))
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)


def render_line_chart(df: pd.DataFrame, time_col: str, num_col: str, group_col: Optional[str] = None, orig_time: str = None, orig_num: str = None, orig_group: str = None):
    """Render interactive line chart for time-series analysis."""
    time_title = (orig_time or time_col).replace("_", " ").title()
    num_title = (orig_num or num_col).replace("_", " ").title()

    plot_df = df.copy()
    
    encode_kwargs = {
        "x": alt.X(f"{time_col}:O", title=time_title),
        "y": alt.Y(f"{num_col}:Q", title=num_title),
        "tooltip": [
            alt.Tooltip(f"{time_col}:O", title=time_title),
            alt.Tooltip(f"{num_col}:Q", title=num_title, format=",.2f")
        ]
    }
    
    if group_col and group_col in plot_df.columns:
        group_title = (orig_group or group_col).replace("_", " ").title()
        encode_kwargs["color"] = alt.Color(f"{group_col}:N", title=group_title)
        encode_kwargs["tooltip"].append(alt.Tooltip(f"{group_col}:N", title=group_title))

    chart = (
        alt.Chart(plot_df)
        .mark_line(point=True)
        .encode(**encode_kwargs)
        .properties(height=380)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)


def render_area_chart(df: pd.DataFrame, time_col: str, num_col: str, orig_time: str = None, orig_num: str = None):
    """Render interactive area chart."""
    time_title = (orig_time or time_col).replace("_", " ").title()
    num_title = (orig_num or num_col).replace("_", " ").title()

    plot_df = df.copy()
    chart = (
        alt.Chart(plot_df)
        .mark_area(
            line={"color": "#1F497D"},
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color="#1F497D", offset=0),
                    alt.GradientStop(color="rgba(31, 73, 125, 0.1)", offset=1)
                ],
                x1=1, x2=1, y1=1, y2=0
            )
        )
        .encode(
            x=alt.X(f"{time_col}:O", title=time_title),
            y=alt.Y(f"{num_col}:Q", title=num_title),
            tooltip=[
                alt.Tooltip(f"{time_col}:O", title=time_title),
                alt.Tooltip(f"{num_col}:Q", title=num_title, format=",.2f")
            ]
        )
        .properties(height=350)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)


def render_auto_visualization(df: pd.DataFrame, key_prefix: str = "default"):
    """
    Main entry point: Automatically inspects data grain and renders
    the most insightful chart, giving users interactive control.
    Accepts unique `key_prefix` to prevent Streamlit DuplicateWidgetID collisions.
    """
    if df.empty:
        st.info("No data available to visualize.")
        return

    # Case 1: Single Scalar Row (e.g. Total count or average)
    if len(df) == 1:
        render_metric_card(df)
        return

    # Sanitize DataFrame for Altair compatibility
    clean_df, col_mapping = sanitize_df_for_altair(df)
    temporal_cols, categorical_cols, numeric_cols = classify_columns(clean_df)

    # If no measurable numeric columns found, fallback to pure tabular view
    if not numeric_cols:
        return

    num_col = numeric_cols[0]
    
    # Determine default chart type
    if temporal_cols:
        default_type = "Line Chart"
    elif categorical_cols:
        default_type = "Bar Chart"
    else:
        default_type = "Bar Chart"

    # Quick interactive chart switcher with unique session key
    col_chart, col_spacer = st.columns([2, 5])
    with col_chart:
        widget_key = f"chart_picker_{key_prefix}_{hash(tuple(clean_df.columns))}_{len(clean_df)}"
        chart_choice = st.selectbox(
            "Chart Type",
            options=["Bar Chart", "Line Chart", "Area Chart"],
            index=["Bar Chart", "Line Chart", "Area Chart"].index(default_type),
            label_visibility="collapsed",
            key=widget_key
        )

    # Render selected chart
    if chart_choice == "Bar Chart":
        cat_col = categorical_cols[0] if categorical_cols else (temporal_cols[0] if temporal_cols else clean_df.columns[0])
        render_bar_chart(clean_df, cat_col, num_col, orig_cat=col_mapping.get(cat_col), orig_num=col_mapping.get(num_col))
    elif chart_choice == "Line Chart":
        time_col = temporal_cols[0] if temporal_cols else (categorical_cols[0] if categorical_cols else clean_df.columns[0])
        group_col = categorical_cols[0] if temporal_cols and categorical_cols else None
        render_line_chart(clean_df, time_col, num_col, group_col, orig_time=col_mapping.get(time_col), orig_num=col_mapping.get(num_col), orig_group=col_mapping.get(group_col) if group_col else None)
    elif chart_choice == "Area Chart":
        time_col = temporal_cols[0] if temporal_cols else (categorical_cols[0] if categorical_cols else clean_df.columns[0])
        render_area_chart(clean_df, time_col, num_col, orig_time=col_mapping.get(time_col), orig_num=col_mapping.get(num_col))
