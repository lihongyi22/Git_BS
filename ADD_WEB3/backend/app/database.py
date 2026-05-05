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
                age INTEGER NOT NULL DEFAULT 18,
                gender TEXT NOT NULL DEFAULT 'Other',
                repeat_count INTEGER NOT NULL DEFAULT 2,
                latin_row INTEGER NOT NULL DEFAULT 1,
                group_number INTEGER NOT NULL DEFAULT 1,
                media_order TEXT NOT NULL DEFAULT 'voice_first',
                current_trial_index INTEGER NOT NULL DEFAULT 0,
                current_module TEXT NOT NULL DEFAULT 'HOME',
                training_completed_at TEXT,
                experiment_started_at TEXT,
                experiment_completed_at TEXT,
                rest_started_at TEXT,
                rest_duration_seconds INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS trial_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id TEXT NOT NULL,
                trial_index INTEGER NOT NULL,
                repetition_no INTEGER NOT NULL,
                module_number INTEGER NOT NULL DEFAULT 1,
                trial_number_in_module INTEGER NOT NULL DEFAULT 1,
                global_trial_number INTEGER NOT NULL DEFAULT 1,
                condition_id TEXT NOT NULL,
                condition_code TEXT NOT NULL DEFAULT '',
                scenario_type TEXT NOT NULL,
                condition_style TEXT NOT NULL,
                condition_media TEXT NOT NULL,
                instance_id INTEGER NOT NULL DEFAULT 1,
                option_order_presented TEXT,
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
                trial_started_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(subject_id) REFERENCES subjects(id)
            );

            CREATE TABLE IF NOT EXISTS trial_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id TEXT NOT NULL,
                trial_index INTEGER NOT NULL,
                condition_id TEXT NOT NULL,
                condition_code TEXT,
                scenario_type TEXT NOT NULL,
                condition_style TEXT NOT NULL,
                condition_media TEXT NOT NULL,
                module_number INTEGER,
                trial_number_in_module INTEGER,
                global_trial_number INTEGER,
                instance_id INTEGER,
                option_order_presented TEXT,
                glucose_profile_key TEXT,
                glucose_trend_label TEXT,
                glucose_variant_index INTEGER,
                initial_action TEXT NOT NULL,
                initial_choice_score REAL,
                initial_confidence INTEGER NOT NULL,
                confidence_before INTEGER,
                advice_shown_at TEXT,
                advice_recommendation TEXT,
                advice_recommendation_score REAL,
                final_action TEXT NOT NULL,
                final_choice_score REAL,
                final_confidence INTEGER NOT NULL,
                confidence_after INTEGER,
                response_time_ms INTEGER NOT NULL,
                trial_duration_seconds REAL,
                initial_quality REAL NOT NULL,
                final_quality REAL NOT NULL,
                quality_delta REAL NOT NULL,
                confidence_delta REAL NOT NULL,
                delta_confidence REAL,
                woa REAL,
                woa_score REAL,
                woa_null_reason TEXT,
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

            CREATE TABLE IF NOT EXISTS audit_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id TEXT NOT NULL,
                changed_by TEXT NOT NULL DEFAULT 'admin',
                change_type TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                reason TEXT NOT NULL
            );
            """
        )

        subject_columns = {
            "group_number": "group_number INTEGER NOT NULL DEFAULT 1",
            "media_order": "media_order TEXT NOT NULL DEFAULT 'voice_first'",
            "training_completed_at": "training_completed_at TEXT",
            "experiment_started_at": "experiment_started_at TEXT",
            "experiment_completed_at": "experiment_completed_at TEXT",
            "rest_started_at": "rest_started_at TEXT",
            "rest_duration_seconds": "rest_duration_seconds INTEGER",
        }
        for name, definition in subject_columns.items():
            _ensure_column(conn, "subjects", name, definition)

        plan_columns = {
            "module_number": "module_number INTEGER NOT NULL DEFAULT 1",
            "trial_number_in_module": "trial_number_in_module INTEGER NOT NULL DEFAULT 1",
            "global_trial_number": "global_trial_number INTEGER NOT NULL DEFAULT 1",
            "condition_code": "condition_code TEXT NOT NULL DEFAULT ''",
            "instance_id": "instance_id INTEGER NOT NULL DEFAULT 1",
            "option_order_presented": "option_order_presented TEXT",
            "trial_started_at": "trial_started_at TEXT",
        }
        for name, definition in plan_columns.items():
            _ensure_column(conn, "trial_plans", name, definition)

        log_columns = {
            "condition_code": "condition_code TEXT",
            "module_number": "module_number INTEGER",
            "trial_number_in_module": "trial_number_in_module INTEGER",
            "global_trial_number": "global_trial_number INTEGER",
            "instance_id": "instance_id INTEGER",
            "option_order_presented": "option_order_presented TEXT",
            "initial_choice_score": "initial_choice_score REAL",
            "confidence_before": "confidence_before INTEGER",
            "advice_shown_at": "advice_shown_at TEXT",
            "advice_recommendation": "advice_recommendation TEXT",
            "advice_recommendation_score": "advice_recommendation_score REAL",
            "final_choice_score": "final_choice_score REAL",
            "confidence_after": "confidence_after INTEGER",
            "trial_duration_seconds": "trial_duration_seconds REAL",
            "delta_confidence": "delta_confidence REAL",
            "woa_score": "woa_score REAL",
            "woa_null_reason": "woa_null_reason TEXT",
        }
        for name, definition in log_columns.items():
            _ensure_column(conn, "trial_logs", name, definition)

        conn.executescript(
            """
            DROP VIEW IF EXISTS participant;
            CREATE VIEW participant AS
            SELECT
                id AS participant_id,
                id AS participant_code,
                group_number,
                media_order,
                latin_row AS latin_square_row,
                training_completed_at,
                experiment_started_at,
                experiment_completed_at,
                created_at
            FROM subjects;

            DROP VIEW IF EXISTS trial;
            CREATE VIEW trial AS
            SELECT
                l.id AS trial_id,
                l.subject_id AS participant_id,
                l.module_number,
                l.trial_number_in_module,
                l.global_trial_number,
                l.condition_code,
                l.scenario_type,
                l.condition_style AS style_type,
                l.condition_media AS media_type,
                l.instance_id,
                l.option_order_presented,
                l.initial_action AS initial_choice,
                l.initial_choice_score,
                l.confidence_before,
                l.advice_shown_at,
                l.advice_recommendation,
                l.advice_recommendation_score,
                l.final_action AS final_choice,
                l.final_choice_score,
                l.confidence_after,
                l.woa_score,
                l.woa_null_reason,
                l.delta_confidence,
                l.created_at AS trial_completed_at,
                l.trial_duration_seconds
            FROM trial_logs l;
            """
        )


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
