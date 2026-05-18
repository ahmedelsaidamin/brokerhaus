"""
Database models for Brokerhaus.
Using raw SQLite for portability — no ORM dependency required.
"""

import sqlite3
import os
import json
from datetime import datetime, timedelta
from contextlib import contextmanager

DB_PATH = os.environ.get("BROKERHAUS_DB", os.path.join(os.path.dirname(__file__), "..", "brokerhaus.db"))


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    with get_db() as conn:
        c = conn.cursor()

        # Users — both candidates and HR
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('candidate','hr','admin')),
            full_name TEXT NOT NULL,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
        """)

        # Candidate profiles
        c.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            code TEXT UNIQUE NOT NULL,
            primary_department TEXT,
            seniority TEXT,
            company_job_title TEXT,
            current_company TEXT,
            work_description TEXT,
            years_total INTEGER DEFAULT 0,
            availability TEXT DEFAULT 'available' CHECK(availability IN ('available','not_available')),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        # Candidate functions (many-to-many of functions selected)
        c.execute("""
        CREATE TABLE IF NOT EXISTS candidate_functions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            department_id TEXT NOT NULL,
            function_name TEXT NOT NULL,
            years_in_function INTEGER DEFAULT 0,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
        )
        """)

        # HR firms
        c.execute("""
        CREATE TABLE IF NOT EXISTS firms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            company_name TEXT NOT NULL,
            verified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        # Nominations sent from HR to candidates
        c.execute("""
        CREATE TABLE IF NOT EXISTS nominations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firm_id INTEGER NOT NULL,
            candidate_id INTEGER NOT NULL,
            search_id INTEGER,
            role_summary TEXT,
            required_department TEXT,
            required_functions TEXT,
            required_seniority TEXT,
            required_years INTEGER,
            match_score REAL,
            status TEXT DEFAULT 'sent' CHECK(status IN ('sent','accepted','declined','expired')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            responded_at TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (firm_id) REFERENCES firms(id) ON DELETE CASCADE,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
        )
        """)

        # Saved searches (so HR can re-run a search)
        c.execute("""
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firm_id INTEGER NOT NULL,
            label TEXT,
            department TEXT,
            functions_json TEXT,
            seniority_levels_json TEXT,
            min_years INTEGER DEFAULT 0,
            max_years INTEGER DEFAULT 50,
            function_years_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (firm_id) REFERENCES firms(id) ON DELETE CASCADE
        )
        """)

        # Sessions (simple token-based)
        c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        # Indices for performance
        c.execute("CREATE INDEX IF NOT EXISTS idx_cf_candidate ON candidate_functions(candidate_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cf_function ON candidate_functions(function_name)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cf_dept ON candidate_functions(department_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cand_dept ON candidates(primary_department)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cand_avail ON candidates(availability)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_nom_candidate ON nominations(candidate_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_nom_firm ON nominations(firm_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_nom_status ON nominations(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")


def expire_old_nominations():
    """Mark nominations older than 30 days as expired. Called on app start."""
    with get_db() as conn:
        conn.execute("""
            UPDATE nominations
            SET status = 'expired'
            WHERE status = 'sent' AND expires_at < CURRENT_TIMESTAMP
        """)
