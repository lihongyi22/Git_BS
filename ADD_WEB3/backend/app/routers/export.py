from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.database import get_conn

router = APIRouter(prefix="/api/export", tags=["export"])

TRIAL_COLUMNS = [
    "participant_code",
    "group_number",
    "latin_square_row",
    "media_order",
    "module_number",
    "trial_number_in_module",
    "global_trial_number",
    "condition_code",
    "scenario_type",
    "style_type",
    "media_type",
    "instance_id",
    "option_order_presented",
    "initial_choice",
    "initial_choice_score",
    "confidence_before",
    "advice_recommendation",
    "advice_recommendation_score",
    "final_choice",
    "final_choice_score",
    "confidence_after",
    "woa_score",
    "delta_confidence",
    "trial_duration_seconds",
]

ALL_EXTRA_COLUMNS = ["experiment_started_at", "experiment_completed_at", "training_completed_at"]


def _csv_response(rows, columns: list[str], filename: str) -> StreamingResponse:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(column, "") for column in columns])
    output.seek(0)
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers=headers)


def _trial_rows(conn, subject_id: str | None = None) -> list[dict]:
    where = "WHERE s.id = ?" if subject_id else ""
    params = (subject_id,) if subject_id else ()
    rows = conn.execute(
        f"""
        SELECT
            s.id AS participant_code,
            s.group_number,
            s.latin_row AS latin_square_row,
            s.media_order,
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
            l.advice_recommendation,
            l.advice_recommendation_score,
            l.final_action AS final_choice,
            l.final_choice_score,
            l.confidence_after,
            l.woa_score,
            l.delta_confidence,
            l.trial_duration_seconds,
            s.experiment_started_at,
            s.experiment_completed_at,
            s.training_completed_at
        FROM subjects s
        LEFT JOIN trial_logs l ON l.subject_id = s.id
        {where}
        ORDER BY s.id, l.global_trial_number
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows if row["global_trial_number"] is not None]


@router.get("/{subject_id}.csv")
def export_subject_csv(subject_id: str) -> StreamingResponse:
    with get_conn() as conn:
        subject = conn.execute("SELECT id FROM subjects WHERE id = ?", (subject_id,)).fetchone()
        if not subject:
            raise HTTPException(status_code=404, detail="subject not found")
        rows = _trial_rows(conn, subject_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _csv_response(rows, TRIAL_COLUMNS, f"participant_{subject_id}_{timestamp}.csv")


@router.get("/all/summary.csv")
def export_all_csv() -> StreamingResponse:
    with get_conn() as conn:
        rows = _trial_rows(conn)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _csv_response(rows, TRIAL_COLUMNS + ALL_EXTRA_COLUMNS, f"participants_all_{timestamp}.csv")
