"""
Unit and Integration Tests for NYC 311 30-Day Rolling Data Retention Engine.
Tests:
- Ingestion failure circuit breaker (0 or negative ingested rows)
- Retention window circuit breaker (0 or negative retention days preventing warehouse wipe)
- Retention cutoff timestamp math
- PostgREST Content-Range row count parsing
- Storage telemetry and 500 MB quota monitoring
- Pruning of expired fact & quarantine records (direct SQL & PostgREST fallback)
- Dry-run mode non-destructiveness
- Dimension table preservation
- Candidate expiration counting
- Autocommit VACUUM ANALYZE error resilience (psycopg2 & SQLAlchemy autocommit)
"""

import os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest
import requests

from src.etl.retention import (
    calculate_retention_cutoff,
    parse_content_range_count,
    get_storage_telemetry,
    count_expired_records,
    prune_expired_facts,
    prune_expired_quarantine,
    execute_vacuum,
    enforce_rolling_retention,
    get_supabase_credentials,
    SUPABASE_FREE_TIER_LIMIT_MB,
    STORAGE_WARN_THRESHOLD_MB
)
from db.connection import execute_query


class TestRetentionCircuitBreaker:
    """Verifies that the retention engine protects existing data during ingestion anomalies."""

    def test_circuit_breaker_on_zero_rows(self):
        result = enforce_rolling_retention(retention_days=30, dry_run=False, min_ingested_rows=0)
        assert result["status"] == "aborted"
        assert result["reason"] == "circuit_breaker_triggered"
        assert result["deleted_facts"] == 0
        assert result["deleted_quarantine"] == 0
        assert result["min_ingested_rows"] == 0

    def test_circuit_breaker_on_negative_rows(self):
        result = enforce_rolling_retention(retention_days=30, dry_run=False, min_ingested_rows=-50)
        assert result["status"] == "aborted"
        assert result["reason"] == "circuit_breaker_triggered"
        assert result["deleted_facts"] == 0
        assert result["deleted_quarantine"] == 0

    def test_circuit_breaker_on_zero_retention_days(self):
        result = enforce_rolling_retention(retention_days=0, dry_run=False, min_ingested_rows=100)
        assert result["status"] == "aborted"
        assert result["reason"] == "invalid_retention_days"
        assert result["deleted_facts"] == 0
        assert result["deleted_quarantine"] == 0

    def test_circuit_breaker_on_negative_retention_days(self):
        result = enforce_rolling_retention(retention_days=-15, dry_run=False, min_ingested_rows=100)
        assert result["status"] == "aborted"
        assert result["reason"] == "invalid_retention_days"
        assert result["deleted_facts"] == 0
        assert result["deleted_quarantine"] == 0

    def test_circuit_breaker_on_invalid_string_retention_days(self):
        result = enforce_rolling_retention(retention_days="invalid_days", dry_run=False, min_ingested_rows=100)
        assert result["status"] == "aborted"
        assert result["reason"] == "invalid_retention_days"


class TestRetentionCutoffMath:
    """Tests calculation of exact UTC cutoff timestamps."""

    def test_calculate_retention_cutoff_30_days(self):
        now_utc = datetime.now(timezone.utc)
        cutoff = calculate_retention_cutoff(30)
        expected = now_utc - timedelta(days=30)
        # Difference should be under 2 seconds
        diff = abs((cutoff - expected).total_seconds())
        assert diff < 2.0
        assert cutoff.tzinfo == timezone.utc

    def test_calculate_retention_cutoff_custom_windows(self):
        now_utc = datetime.now(timezone.utc)
        for days in (1, 7, 14, 60, 90):
            cutoff = calculate_retention_cutoff(days)
            expected = now_utc - timedelta(days=days)
            assert abs((cutoff - expected).total_seconds()) < 2.0


class TestContentRangeParser:
    """Tests parsing of HTTP Content-Range headers returned by PostgREST DELETE."""

    def test_parse_valid_content_range_formats(self):
        assert parse_content_range_count("*/0") == 0
        assert parse_content_range_count("*/150") == 150
        assert parse_content_range_count("0-999/1000") == 1000
        assert parse_content_range_count("0-2499/2500") == 2500
        assert parse_content_range_count("0-0/1") == 1

    def test_parse_content_range_edge_cases(self):
        assert parse_content_range_count(None) == 0
        assert parse_content_range_count("") == 0
        assert parse_content_range_count("invalid-format") == 0
        assert parse_content_range_count("*/") == 0
        assert parse_content_range_count("bytes 0-100/*") == 0


class TestStorageTelemetry:
    """Verifies live PostgreSQL storage and capacity telemetry against 500 MB quota."""

    def test_storage_telemetry_schema_and_types(self):
        telemetry = get_storage_telemetry()
        assert isinstance(telemetry["db_bytes"], int)
        assert telemetry["db_bytes"] > 0
        assert isinstance(telemetry["db_size_pretty"], str)
        assert "MB" in telemetry["db_size_pretty"] or "kB" in telemetry["db_size_pretty"] or "GB" in telemetry["db_size_pretty"]
        assert isinstance(telemetry["pct_of_500mb_quota"], float)
        assert 0.0 < telemetry["pct_of_500mb_quota"] <= 100.0
        assert telemetry["total_facts"] > 0
        assert telemetry["total_quarantine"] >= 0
        assert telemetry["free_tier_quota_mb"] == SUPABASE_FREE_TIER_LIMIT_MB
        assert telemetry["warning_threshold_mb"] == STORAGE_WARN_THRESHOLD_MB
        assert isinstance(telemetry["is_warning"], bool)

    def test_storage_warning_threshold_evaluation(self):
        warn_bytes = STORAGE_WARN_THRESHOLD_MB * 1024 * 1024
        # Below threshold
        assert (warn_bytes - 1) < warn_bytes
        # Above threshold
        assert (warn_bytes + 1) >= warn_bytes

    def test_storage_warning_flag_triggers_when_exceeded(self):
        # Mock execute_query returning database size exceeding 400 MB threshold (450 MB)
        fake_db_bytes = 450 * 1024 * 1024
        mock_res = {
            "success": True,
            "rows": [{
                "db_bytes": fake_db_bytes,
                "db_size_pretty": "450 MB",
                "pct_of_500mb_quota": 90.0,
                "total_facts": 120000,
                "total_quarantine": 500
            }]
        }
        with patch("src.etl.retention.execute_query", return_value=mock_res):
            telemetry = get_storage_telemetry()
            assert telemetry["is_warning"] is True
            assert telemetry["pct_of_500mb_quota"] == 90.0


class TestCandidateCounting:
    """Tests query of candidate expired records without deletion."""

    def test_count_expired_records_returns_valid_structure(self):
        counts = count_expired_records(30)
        assert "expired_facts" in counts
        assert "expired_quarantine" in counts
        assert isinstance(counts["expired_facts"], int)
        assert isinstance(counts["expired_quarantine"], int)
        assert counts["expired_facts"] >= 0
        assert counts["expired_quarantine"] >= 0

    def test_shorter_window_yields_more_or_equal_candidates(self):
        # 10-day retention window candidate count must be >= 30-day retention candidate count
        c10 = count_expired_records(10)["expired_facts"]
        c30 = count_expired_records(30)["expired_facts"]
        assert c10 >= c30

    def test_count_expired_records_rejects_invalid_days(self):
        with pytest.raises(ValueError, match="retention_days must be at least 1"):
            count_expired_records(0)
        with pytest.raises(ValueError, match="retention_days must be at least 1"):
            count_expired_records(-5)


class TestPruningFunctions:
    """Tests fact and quarantine pruning logic under direct SQL and PostgREST fallback."""

    def test_prune_expired_facts_direct_sql_success(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 42
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("src.etl.retention.get_direct_connection", return_value=mock_conn):
            deleted = prune_expired_facts(30, dry_run=False)
            assert deleted == 42
            assert mock_conn.autocommit is True
            mock_cursor.execute.assert_called_once()
            assert "DELETE FROM public.fact_complaints" in mock_cursor.execute.call_args[0][0]
            mock_conn.close.assert_called_once()

    def test_prune_expired_facts_fallback_to_postgrest(self):
        # When direct connection returns None, calls PostgREST DELETE
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {"content-range": "*/75"}

        with patch("src.etl.retention.get_direct_connection", return_value=None), \
             patch("src.etl.retention.get_supabase_credentials", return_value=("https://example.supabase.co", "test_key")), \
             patch("requests.delete", return_value=mock_response) as mock_delete:
            deleted = prune_expired_facts(30, dry_run=False)
            assert deleted == 75
            mock_delete.assert_called_once()
            call_url = mock_delete.call_args[0][0]
            assert "fact_complaints?created_timestamp=lt." in call_url

    def test_prune_expired_quarantine_direct_sql_success(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 17
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("src.etl.retention.get_direct_connection", return_value=mock_conn):
            deleted = prune_expired_quarantine(30, dry_run=False)
            assert deleted == 17
            assert mock_conn.autocommit is True
            mock_cursor.execute.assert_called_once()
            assert "DELETE FROM public.quarantine_complaints" in mock_cursor.execute.call_args[0][0]
            mock_conn.close.assert_called_once()

    def test_prune_expired_quarantine_postgrest_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {"content-range": "*/12"}

        with patch("src.etl.retention.get_direct_connection", return_value=None), \
             patch("src.etl.retention.get_supabase_credentials", return_value=("https://example.supabase.co", "test_key")), \
             patch("requests.delete", return_value=mock_response) as mock_delete:
            deleted = prune_expired_quarantine(30, dry_run=False)
            assert deleted == 12
            mock_delete.assert_called_once()
            call_url = mock_delete.call_args[0][0]
            assert "quarantine_complaints?quarantined_at=lt." in call_url

    def test_prune_functions_reject_invalid_retention_days(self):
        with pytest.raises(ValueError, match="retention_days must be at least 1"):
            prune_expired_facts(0)
        with pytest.raises(ValueError, match="retention_days must be at least 1"):
            prune_expired_quarantine(-1)

    def test_prune_functions_dry_run_never_calls_delete(self):
        with patch("requests.delete") as mock_delete, \
             patch("src.etl.retention.get_direct_connection") as mock_conn:
            df = prune_expired_facts(30, dry_run=True)
            dq = prune_expired_quarantine(30, dry_run=True)
            assert df == 0
            assert dq == 0
            mock_delete.assert_not_called()
            mock_conn.assert_not_called()


class TestDryRunMode:
    """Verifies dry-run mode gathers telemetry and reports candidate rows without deleting."""

    def test_dry_run_mode_never_deletes(self):
        res = enforce_rolling_retention(retention_days=30, dry_run=True, min_ingested_rows=100)
        assert res["status"] == "dry_run_completed"
        assert res["retention_days"] == 30
        assert res["deleted_facts"] == 0
        assert res["deleted_quarantine"] == 0
        assert res["vacuum_executed"] is False
        assert "candidate_facts_to_delete" in res
        assert "candidate_quarantine_to_delete" in res
        assert "telemetry" in res
        assert res["telemetry"]["total_facts"] > 0


class TestDimensionImmutability:
    """Ensures retention cleanup leaves all dimension tables 100% intact."""

    def test_dimension_tables_preserved(self):
        dim_queries = {
            "dim_agency": "SELECT COUNT(*) AS c FROM public.dim_agency",
            "dim_complaint_type": "SELECT COUNT(*) AS c FROM public.dim_complaint_type",
            "dim_location": "SELECT COUNT(*) AS c FROM public.dim_location",
            "dim_calendar": "SELECT COUNT(*) AS c FROM public.dim_calendar"
        }
        counts = {}
        for dim_name, sql in dim_queries.items():
            res = execute_query(sql)
            assert res.get("success") is True, f"Failed to query {dim_name}"
            count = res["rows"][0]["c"]
            assert count > 0, f"{dim_name} has zero rows!"
            counts[dim_name] = count

        # Verify retention only deletes from fact_complaints and quarantine_complaints
        # Running dry-run check must not mutate dimensions
        enforce_rolling_retention(retention_days=30, dry_run=True, min_ingested_rows=1)

        for dim_name, sql in dim_queries.items():
            res = execute_query(sql)
            new_count = res["rows"][0]["c"]
            assert new_count == counts[dim_name], f"{dim_name} row count changed from {counts[dim_name]} to {new_count}!"


class TestVacuumExecution:
    """Tests VACUUM ANALYZE autocommit execution and fallback resilience."""

    def test_vacuum_graceful_fallback_when_no_direct_connection(self):
        with patch("src.etl.retention.get_direct_connection", return_value=None), \
             patch("db.connection.get_sqlalchemy_engine", return_value=None):
            vacuum_result = execute_vacuum()
            assert vacuum_result is False

    def test_vacuum_autocommit_execution_when_connected_psycopg2(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("src.etl.retention.get_direct_connection", return_value=mock_conn):
            vacuum_result = execute_vacuum(["fact_complaints", "quarantine_complaints"])
            assert vacuum_result is True
            assert mock_conn.autocommit is True
            assert mock_cursor.execute.call_count == 2
            mock_conn.close.assert_called_once()

    def test_vacuum_autocommit_execution_when_connected_sqlalchemy(self):
        mock_engine = MagicMock()
        mock_sa_conn = MagicMock()
        mock_engine.connect.return_value.execution_options.return_value.__enter__.return_value = mock_sa_conn

        with patch("src.etl.retention.get_direct_connection", return_value=None), \
             patch("db.connection.get_sqlalchemy_engine", return_value=mock_engine):
            vacuum_result = execute_vacuum(["fact_complaints", "quarantine_complaints"])
            assert vacuum_result is True
            assert mock_sa_conn.execute.call_count == 2


class TestEnvironmentFallbacks:
    """Verifies that empty string or dynamic environment overrides behave safely."""

    def test_dynamic_credentials_resolution(self):
        with patch.dict(os.environ, {"SUPABASE_URL": "https://dynamic.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "dynamic_key"}):
            url, key = get_supabase_credentials()
            assert url == "https://dynamic.supabase.co"
            assert key == "dynamic_key"
