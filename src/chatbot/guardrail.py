"""
SQL AST & Regex Security Guardrail Module
Validates, sanitizes, and enforces read-only invariants on AI-generated SQL queries
before execution against the Supabase PostgreSQL database.
"""

import re
from typing import Tuple, Optional

# Strict list of prohibited DDL, DML, and administrative keywords
FORBIDDEN_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
    "GRANT", "REVOKE", "COPY", "CREATE", "REPLACE", "EXEC",
    "EXECUTE", "CALL", "VACUUM", "COMMENT", "LOCK", "SET",
    "DO", "BEGIN", "COMMIT", "ROLLBACK", "MERGE"
}

# Forbidden system catalog tables and security-sensitive namespaces
FORBIDDEN_TABLES = {
    "pg_shadow", "pg_authid", "pg_user", "pg_roles", "pg_database",
    "pg_tablespace", "pg_stat_activity", "information_schema.user_mappings"
}

MAX_ROW_LIMIT = 100


class SecurityViolationError(Exception):
    """Raised when a SQL query violates read-only AST guardrail rules."""
    pass


def strip_sql_comments(sql: str) -> str:
    """Remove single-line (--) and multi-line (/* */) SQL comments."""
    # Remove multi-line comments
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    # Remove single-line comments
    sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
    return sql.strip()


def validate_single_statement(sql: str) -> str:
    """
    Ensure the query contains exactly one SQL statement.
    Rejects chained queries (semicolon abuse / SQL injection).
    """
    clean = sql.strip()
    if clean.endswith(";"):
        clean = clean[:-1].strip()
        
    # Check for unquoted semicolons
    in_single_quote = False
    in_double_quote = False
    for char in clean:
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif char == ";" and not in_single_quote and not in_double_quote:
            raise SecurityViolationError("Multiple SQL statements detected (semicolon chaining is prohibited).")
            
    return clean


def enforce_read_only_ast(sql: str) -> str:
    """
    Parse SQL tokens and verify that statement is strictly a SELECT query.
    Blocks all mutation, administrative, and data exfiltration patterns.
    """
    stripped = strip_sql_comments(sql)
    if not stripped:
        raise SecurityViolationError("Empty SQL query provided.")

    single_statement = validate_single_statement(stripped)

    # Tokenize words outside quoted literals
    tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", single_statement)
    if not tokens:
        raise SecurityViolationError("No valid SQL tokens found.")

    first_keyword = tokens[0].upper()
    if first_keyword not in ("SELECT", "WITH"):
        raise SecurityViolationError(f"Prohibited statement type '{first_keyword}'. Only SELECT and WITH queries are authorized.")

    # Check for forbidden keywords anywhere in token stream
    upper_tokens = [t.upper() for t in tokens]
    for kw in upper_tokens:
        if kw in FORBIDDEN_KEYWORDS:
            raise SecurityViolationError(f"Security violation: Prohibited keyword '{kw}' detected.")

    # Check for forbidden system catalogs
    lower_sql = single_statement.lower()
    for sys_tbl in FORBIDDEN_TABLES:
        if re.search(r"\b" + re.escape(sys_tbl) + r"\b", lower_sql):
            raise SecurityViolationError(f"Access to sensitive system catalog '{sys_tbl}' is strictly blocked.")

    # Check for 'INTO' clause (prevent SELECT INTO table creation)
    if re.search(r"\bINTO\b", single_statement, re.IGNORECASE):
        # Ensure it's not inside a string literal
        if not re.search(r"'.*?\bINTO\b.*?'", single_statement, re.IGNORECASE):
            raise SecurityViolationError("SELECT INTO statements are prohibited.")

    return single_statement


def enforce_limit_clause(sql: str, max_limit: int = MAX_ROW_LIMIT) -> str:
    """
    Ensure the query has an enforced LIMIT clause capped at max_limit.
    Appends LIMIT max_limit if absent, or caps existing limit if it exceeds max_limit.
    """
    # Regex to find existing LIMIT clause at the end of query
    limit_match = re.search(r"\bLIMIT\s+(\d+)\b", sql, re.IGNORECASE)
    
    if limit_match:
        current_limit = int(limit_match.group(1))
        if current_limit > max_limit or current_limit <= 0:
            # Replace existing limit with capped max_limit
            sql = re.sub(r"\bLIMIT\s+\d+\b", f"LIMIT {max_limit}", sql, flags=re.IGNORECASE)
    else:
        # Append LIMIT clause
        sql = f"{sql} LIMIT {max_limit}"
        
    return sql


def sanitize_and_guard_query(raw_sql: str) -> str:
    """
    Master pipeline: Strip markdown code blocks, enforce read-only AST,
    and enforce row cap. Returns safe, production-ready SQL.
    """
    # Strip markdown formatting (e.g. ```sql ... ```)
    clean = re.sub(r"^```(?:sql)?\s*", "", raw_sql.strip(), flags=re.IGNORECASE)
    clean = re.sub(r"\s*```$", "", clean.strip())
    
    # Enforce read-only AST
    guarded = enforce_read_only_ast(clean)
    
    # Enforce row limit
    final_sql = enforce_limit_clause(guarded, MAX_ROW_LIMIT)
    
    return final_sql
