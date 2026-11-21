"""
Database package for NYC 311 Analytics Application.
Provides dual-mode PostgreSQL connectivity and query builders.
"""
from db.connection import execute_query, check_connection

__all__ = ["execute_query", "check_connection"]
