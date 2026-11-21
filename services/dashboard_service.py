"""
Dashboard Service Layer for NYC 311 Executive Analytics.
Manages TTL-based caching (@st.cache_data(ttl=3600)), filter state compilation,
and conversion of database records into lightweight DataFrames.
"""

import os
from typing import Dict, Any, List, Optional
import pandas as pd
import streamlit as st
from db.queries import (
    fetch_data_freshness,
    fetch_filter_options,
    fetch_executive_kpis,
    fetch_volume_trend,
    fetch_top_complaint_types,
    fetch_agency_performance,
    fetch_geographic_breakdown,
    fetch_channel_operational_metrics
)

# Configurable TTL Cache (Default 1 hour / 3600 seconds)
CACHE_TTL = int(os.getenv("DASHBOARD_CACHE_TTL", "3600"))


def _normalize_filter_key(filters: Optional[Dict[str, Any]]) -> tuple:
    """Convert mutable filters dict into a hashable cache key."""
    if not filters:
        return ()
    key_items = []
    for k in sorted(filters.keys()):
        v = filters[k]
        if isinstance(v, (list, tuple)):
            key_items.append((k, tuple(sorted(str(x) for x in v))))
        elif isinstance(v, dict):
            key_items.append((k, tuple(sorted((dk, str(dv)) for dk, dv in v.items()))))
        else:
            key_items.append((k, str(v)))
    return tuple(key_items)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_freshness() -> Dict[str, Any]:
    """Retrieve real-time data ingestion and pipeline health statistics."""
    return fetch_data_freshness()


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_filter_options() -> Dict[str, Any]:
    """Retrieve distinct filter options for boroughs, agencies, categories, and dates."""
    return fetch_filter_options()


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _cached_kpis(filter_tuple: tuple, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return fetch_executive_kpis(filters)


def get_kpis(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Retrieve executive KPI metrics with period-over-period deltas."""
    return _cached_kpis(_normalize_filter_key(filters), filters)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _cached_volume_trend(filter_tuple: tuple, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    return fetch_volume_trend(filters)


def get_volume_trend_data(filters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """Retrieve daily volume trend with 7-day rolling average as a DataFrame."""
    rows = _cached_volume_trend(_normalize_filter_key(filters), filters)
    if not rows:
        return pd.DataFrame(columns=["full_date", "complaint_volume", "rolling_7d_avg"])
    df = pd.DataFrame(rows)
    df["full_date"] = pd.to_datetime(df["full_date"])
    return df


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _cached_top_complaints(filter_tuple: tuple, filters: Optional[Dict[str, Any]] = None, limit: int = 15) -> List[Dict[str, Any]]:
    return fetch_top_complaint_types(filters, limit=limit)


def get_top_complaints_data(filters: Optional[Dict[str, Any]] = None, limit: int = 15) -> pd.DataFrame:
    """Retrieve top complaint types and categories as a DataFrame."""
    rows = _cached_top_complaints(_normalize_filter_key(filters), filters, limit)
    if not rows:
        return pd.DataFrame(columns=["complaint_type", "complaint_category", "complaint_count"])
    return pd.DataFrame(rows)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _cached_agency_matrix(filter_tuple: tuple, filters: Optional[Dict[str, Any]] = None, min_volume: int = 20) -> List[Dict[str, Any]]:
    return fetch_agency_performance(filters, min_volume=min_volume)


def get_agency_performance_data(filters: Optional[Dict[str, Any]] = None, min_volume: int = 20) -> pd.DataFrame:
    """Retrieve agency performance matrix as a DataFrame."""
    rows = _cached_agency_matrix(_normalize_filter_key(filters), filters, min_volume)
    if not rows:
        return pd.DataFrame(columns=["agency_name", "agency_code", "total_complaints", "closure_rate", "sla_compliance_rate", "avg_resolution_hours"])
    return pd.DataFrame(rows)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _cached_geographic_breakdown(filter_tuple: tuple, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return fetch_geographic_breakdown(filters)


def get_geographic_data(filters: Optional[Dict[str, Any]] = None) -> Dict[str, pd.DataFrame]:
    """Retrieve geographic breakdown dataframes: boroughs, top zip codes, and coordinate clusters."""
    data = _cached_geographic_breakdown(_normalize_filter_key(filters), filters)
    return {
        "boroughs": pd.DataFrame(data.get("boroughs", [])),
        "top_zips": pd.DataFrame(data.get("top_zips", [])),
        "clusters": pd.DataFrame(data.get("clusters", []))
    }


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _cached_channel_metrics(filter_tuple: tuple, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return fetch_channel_operational_metrics(filters)


def get_channel_metrics_data(filters: Optional[Dict[str, Any]] = None) -> Dict[str, pd.DataFrame]:
    """Retrieve channel distribution and weekday vs weekend metrics dataframes."""
    data = _cached_channel_metrics(_normalize_filter_key(filters), filters)
    return {
        "channels": pd.DataFrame(data.get("channels", [])),
        "weekday_vs_weekend": pd.DataFrame(data.get("weekday_vs_weekend", []))
    }


def clear_dashboard_cache() -> None:
    """Manually clear all Streamlit cached data to force fresh queries from PostgreSQL."""
    st.cache_data.clear()
