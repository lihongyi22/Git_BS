from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DB_PATH = Path(__file__).resolve().parents[1] / "exp_thesis_py.db"


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_def: str) -> None:
    if column_name not in _table_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS subjects (
                id TEXT PRIMARY KEY,
                name TEXT,
                phone TEXT,
                national_id TEXT,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                repeat_count INTEGER NOT NULL DEFAULT 2,
                latin_row INTEGER NOT NULL,
                current_trial_index INTEGER NOT NULL DEFAULT 0,
                current_module TEXT NOT NULL DEFAULT 'HOME',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS trial_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id TEXT NOT NULL,
                trial_index INTEGER NOT NULL,
                repetition_no INTEGER NOT NULL,
                condition_id TEXT NOT NULL,
                scenario_type TEXT NOT NULL,
                condition_style TEXT NOT NULL,
                condition_media TEXT NOT NULL,
                glucose_profile_key TEXT,
                glucose_trend_label TEXT,
                glucose_variant_index INTEGER,
                trigger_glucose REAL NOT NULL,
                glucose_30 REAL NOT NULL,
                glucose_60 REAL NOT NULL,
                glucose_series_json TEXT,
                glucose_outcome_json TEXT,
                recommended_action TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(subject_id) REFERENCES subjects(id)
            );

            CREATE TABLE IF NOT EXISTS trial_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id TEXT NOT NULL,
                trial_index INTEGER NOT NULL,
                condition_id TEXT NOT NULL,
                scenario_type TEXT NOT NULL,
                condition_style TEXT NOT NULL,
                condition_media TEXT NOT NULL,
                glucose_profile_key TEXT,
                glucose_trend_label TEXT,
                glucose_variant_index INTEGER,
                initial_action TEXT NOT NULL,
                initial_confidence INTEGER NOT NULL,
                final_action TEXT NOT NULL,
                final_confidence INTEGER NOT NULL,
                response_time_ms INTEGER NOT NULL,
                initial_quality REAL NOT NULL,
                final_quality REAL NOT NULL,
                quality_delta REAL NOT NULL,
                confidence_delta REAL NOT NULL,
                woa REAL,
                woe REAL,
                advice_start_ts INTEGER,
                advice_end_ts INTEGER,
                final_choice_ts INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(subject_id) REFERENCES subjects(id)
            );

            CREATE TABLE IF NOT EXISTS surveys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id TEXT NOT NULL,
                survey_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(subject_id) REFERENCES subjects(id)
            );
            """
        )

        _ensure_column(conn, "subjects", "name", "name TEXT")
        _ensure_column(conn, "subjects", "phone", "phone TEXT")
        _ensure_column(conn, "subjects", "national_id", "national_id TEXT")
        _ensure_column(conn, "subjects", "repeat_count", "repeat_count INTEGER NOT NULL DEFAULT 2")
        _ensure_column(conn, "subjects", "latin_row", "latin_row INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "subjects", "current_module", "current_module TEXT NOT NULL DEFAULT 'HOME'")

        _ensure_column(conn, "trial_plans", "glucose_series_json", "glucose_series_json TEXT")
        _ensure_column(conn, "trial_plans", "glucose_outcome_json", "glucose_outcome_json TEXT")
        _ensure_column(conn, "trial_plans", "glucose_profile_key", "glucose_profile_key TEXT")
        _ensure_column(conn, "trial_plans", "glucose_trend_label", "glucose_trend_label TEXT")
        _ensure_column(conn, "trial_plans", "glucose_variant_index", "glucose_variant_index INTEGER")

        _ensure_column(conn, "trial_logs", "glucose_profile_key", "glucose_profile_key TEXT")
        _ensure_column(conn, "trial_logs", "glucose_trend_label", "glucose_trend_label TEXT")
        _ensure_column(conn, "trial_logs", "glucose_variant_index", "glucose_variant_index INTEGER")


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
