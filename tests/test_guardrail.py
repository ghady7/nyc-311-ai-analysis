"""
Adversarial SQL Injection & Guardrail Test Suite
Verifies 100% rejection rate for DDL, DML, administrative commands,
statement chaining, and system catalog exfiltration attempts.
"""

import pytest
from src.chatbot.guardrail import (
    sanitize_and_guard_query,
    SecurityViolationError,
    enforce_read_only_ast,
    enforce_limit_clause
)


class TestSQLGuardrailSecurity:

    def test_valid_simple_select(self):
        sql = "SELECT * FROM fact_complaints"
        res = sanitize_and_guard_query(sql)
        assert res == "SELECT * FROM fact_complaints LIMIT 100"

    def test_valid_select_with_existing_reasonable_limit(self):
        sql = "SELECT unique_key, agency_key FROM fact_complaints LIMIT 10"
        res = sanitize_and_guard_query(sql)
        assert res == "SELECT unique_key, agency_key FROM fact_complaints LIMIT 10"

    def test_valid_select_with_excessive_limit_capped(self):
        sql = "SELECT * FROM fact_complaints LIMIT 50000"
        res = sanitize_and_guard_query(sql)
        assert res == "SELECT * FROM fact_complaints LIMIT 100"

    def test_valid_cte_query(self):
        sql = """
        WITH agency_totals AS (
            SELECT agency_key, COUNT(*) AS cnt 
            FROM fact_complaints 
            GROUP BY agency_key
        )
        SELECT * FROM agency_totals ORDER BY cnt DESC;
        """
        res = sanitize_and_guard_query(sql)
        assert "agency_totals" in res
        assert res.endswith("LIMIT 100")

    def test_markdown_codeblock_stripping(self):
        sql = "```sql\nSELECT borough, COUNT(*) FROM dim_location GROUP BY borough\n```"
        res = sanitize_and_guard_query(sql)
        assert res.startswith("SELECT")
        assert res.endswith("LIMIT 100")

    # --- ADVERSARIAL ATTACK TESTS ---

    def test_reject_drop_table(self):
        with pytest.raises(SecurityViolationError, match="Prohibited statement type 'DROP'"):
            sanitize_and_guard_query("DROP TABLE fact_complaints;")

    def test_reject_delete_all(self):
        with pytest.raises(SecurityViolationError, match="Prohibited statement type 'DELETE'"):
            sanitize_and_guard_query("DELETE FROM fact_complaints WHERE 1=1;")

    def test_reject_update(self):
        with pytest.raises(SecurityViolationError, match="Prohibited statement type 'UPDATE'"):
            sanitize_and_guard_query("UPDATE fact_complaints SET status = 'Closed';")

    def test_reject_insert(self):
        with pytest.raises(SecurityViolationError, match="Prohibited statement type 'INSERT'"):
            sanitize_and_guard_query("INSERT INTO fact_complaints (unique_key) VALUES ('HACK');")

    def test_reject_alter(self):
        with pytest.raises(SecurityViolationError, match="Prohibited statement type 'ALTER'"):
            sanitize_and_guard_query("ALTER ROLE readonly_app SUPERUSER;")

    def test_reject_truncate(self):
        with pytest.raises(SecurityViolationError, match="Prohibited statement type 'TRUNCATE'"):
            sanitize_and_guard_query("TRUNCATE TABLE fact_complaints;")

    def test_reject_chained_semicolon_injection(self):
        sql = "SELECT * FROM fact_complaints; DROP TABLE dim_agency;"
        with pytest.raises(SecurityViolationError, match="Multiple SQL statements detected"):
            sanitize_and_guard_query(sql)

    def test_reject_chained_injection_with_spaces(self):
        sql = "SELECT 1 ; DELETE FROM dim_location"
        with pytest.raises(SecurityViolationError, match="Multiple SQL statements detected"):
            sanitize_and_guard_query(sql)

    def test_reject_comment_evasion_attack(self):
        sql = "SELECT 1; -- comment\nDROP TABLE fact_complaints;"
        with pytest.raises(SecurityViolationError):
            sanitize_and_guard_query(sql)

    def test_reject_select_into_creation(self):
        sql = "SELECT * INTO stolen_complaints FROM fact_complaints"
        with pytest.raises(SecurityViolationError, match="SELECT INTO statements are prohibited"):
            sanitize_and_guard_query(sql)

    def test_reject_pg_shadow_exfiltration(self):
        sql = "SELECT usename, passwd FROM pg_shadow"
        with pytest.raises(SecurityViolationError, match="Access to sensitive system catalog 'pg_shadow'"):
            sanitize_and_guard_query(sql)

    def test_reject_pg_authid_exfiltration(self):
        sql = "SELECT * FROM pg_authid"
        with pytest.raises(SecurityViolationError, match="Access to sensitive system catalog 'pg_authid'"):
            sanitize_and_guard_query(sql)

    def test_reject_grant_privileges(self):
        sql = "GRANT ALL ON SCHEMA public TO PUBLIC;"
        with pytest.raises(SecurityViolationError, match="Prohibited statement type 'GRANT'"):
            sanitize_and_guard_query(sql)

    def test_reject_embedded_subquery_delete(self):
        sql = "SELECT * FROM fact_complaints WHERE unique_key IN (DELETE FROM dim_agency RETURNING agency_code)"
        with pytest.raises(SecurityViolationError, match="Prohibited keyword 'DELETE'"):
            sanitize_and_guard_query(sql)
