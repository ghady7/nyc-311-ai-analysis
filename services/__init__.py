"""
Services package for NYC 311 Analytics Application.
Provides cached dashboard analytics and Text-to-SQL AI copilot services.
"""
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

__all__ = [
    "get_freshness",
    "get_filter_options",
    "get_kpis",
    "get_volume_trend_data",
    "get_top_complaints_data",
    "get_agency_performance_data",
    "get_geographic_data",
    "get_channel_metrics_data",
    "clear_dashboard_cache"
]
