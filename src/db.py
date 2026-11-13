"""SQLite persistence layer for Job Radar.

All writes use parameterized SQL. The database is created locally at data/job_radar.db.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "job_radar.db"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'Manual',
    original_url TEXT,
    source_job_id TEXT,
    source_attribution TEXT,
    role_family TEXT,
    eligibility_status TEXT NOT NULL DEFAULT 'REVIEW',
    eligibility_reason TEXT,
    eligibility_evidence TEXT,
    eligibility_checked_at TEXT,
    vacancy_status TEXT,
    job_description TEXT NOT NULL,
    location TEXT,
    work_mode TEXT,
    employment_type TEXT,
    compensation TEXT,
    posted_at TEXT,
    posted_at_evidence TEXT,
    discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    freshness_bucket TEXT,
    applicant_count TEXT,
    status TEXT NOT NULL DEFAULT 'Saved',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    resume_type TEXT NOT NULL,
    file_path TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    resume_id INTEGER NOT NULL REFERENCES resumes(id),
    decision TEXT NOT NULL CHECK(decision IN ('APPLY','APPLY WITH CAUTION','DO NOT APPLY','PENDING')),
    fit_score INTEGER CHECK(fit_score BETWEEN 0 AND 100),
    strengths TEXT,
    gaps TEXT,
    screening_risks TEXT,
    ats_keywords TEXT,
    tailoring_actions TEXT,
    rationale TEXT,
    assessment_version TEXT NOT NULL DEFAULT 'manual-v1',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_id, resume_id, assessment_version)
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    resume_id INTEGER REFERENCES resumes(id),
    assessment_id INTEGER REFERENCES assessments(id),
    status TEXT NOT NULL DEFAULT 'Preparing',
    applied_at TEXT,
    application_channel TEXT,
    expected_compensation TEXT,
    offered_compensation TEXT,
    next_follow_up_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    interaction_type TEXT NOT NULL,
    contact_name TEXT,
    contact_role TEXT,
    contact_channel TEXT,
    occurred_at TEXT NOT NULL,
    summary TEXT NOT NULL,
    response TEXT,
    next_action TEXT,
    next_action_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    round_name TEXT NOT NULL,
    scheduled_at TEXT,
    interviewer TEXT,
    topics TEXT,
    questions TEXT,
    feedback TEXT,
    result TEXT NOT NULL DEFAULT 'Pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL UNIQUE REFERENCES applications(id) ON DELETE CASCADE,
    outcome TEXT NOT NULL,
    reason TEXT,
    feedback TEXT,
    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS improvement_experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hypothesis TEXT NOT NULL,
    change_made TEXT NOT NULL,
    cohort_start TEXT,
    cohort_end TEXT,
    applications_count INTEGER,
    responses_count INTEGER,
    interviews_count INTEGER,
    result TEXT,
    status TEXT NOT NULL DEFAULT 'Planned',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_syncs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    imported_count INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_discovered ON jobs(discovered_at);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_interactions_followup ON interactions(next_action_at);
CREATE INDEX IF NOT EXISTS idx_assessments_job ON assessments(job_id);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive migrations preserve existing local job/application records."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
    additions = {
        "source_job_id": "TEXT",
        "source_attribution": "TEXT",
        "role_family": "TEXT",
        "eligibility_status": "TEXT NOT NULL DEFAULT 'REVIEW'",
        "eligibility_reason": "TEXT",
        "eligibility_evidence": "TEXT",
        "eligibility_checked_at": "TEXT",
        "vacancy_status": "TEXT",
    }
    for name, definition in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {definition}")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_source_identity ON jobs(source, source_job_id) WHERE source_job_id IS NOT NULL")

def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.execute(
            "INSERT OR IGNORE INTO resumes(name, resume_type, notes) VALUES (?, ?, ?)",
            ("Project Manager Resume", "Project Manager", "Primary project delivery resume"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO resumes(name, resume_type, notes) VALUES (?, ?, ?)",
            ("Associate Product Manager Resume", "Associate Product Manager", "Secondary comparison resume"),
        )

def execute(query: str, params: tuple[Any, ...] = ()) -> int:
    with connect() as conn:
        cur = conn.execute(query, params)
        return int(cur.lastrowid or 0)

def query_df(query: str, params: tuple[Any, ...] = ()):
    import pandas as pd
    with connect() as conn:
        return pd.read_sql_query(query, conn, params=params)

def query_one(query: str, params: tuple[Any, ...] = ()):
    with connect() as conn:
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None
