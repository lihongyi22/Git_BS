from __future__ import annotations

import csv
import io

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.database import get_conn

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/{subject_id}.csv")
def export_subject_csv(subject_id: str) -> StreamingResponse:
    with get_conn() as conn:
        subject = conn.execute("SELECT id FROM subjects WHERE id = ?", (subject_id,)).fetchone()
        if not subject:
            raise HTTPException(status_code=404, detail="subject not found")

        rows = conn.execute(
            """
            SELECT trial_index, condition_id, scenario_type, condition_style, condition_media,
                 glucose_profile_key, glucose_trend_label, glucose_variant_index,
                   initial_action, initial_confidence, final_action, final_confidence,
                   initial_quality, final_quality, quality_delta, confidence_delta,
                   woa, woe, response_time_ms, created_at
            FROM trial_logs
            WHERE subject_id = ?
            ORDER BY trial_index
            """,
            (subject_id,),
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "trial_index",
        "condition_id",
        "scenario_type",
        "condition_style",
        "condition_media",
        "glucose_profile_key",
        "glucose_trend_label",
        "glucose_variant_index",
        "initial_action",
        "initial_confidence",
        "final_action",
        "final_confidence",
        "initial_quality",
        "final_quality",
        "quality_delta",
        "confidence_delta",
        "woa",
        "woe",
        "response_time_ms",
        "created_at",
    ])

    for row in rows:
        writer.writerow([
            row["trial_index"],
            row["condition_id"],
            row["scenario_type"],
            row["condition_style"],
            row["condition_media"],
            row["glucose_profile_key"],
            row["glucose_trend_label"],
            row["glucose_variant_index"],
            row["initial_action"],
            row["initial_confidence"],
            row["final_action"],
            row["final_confidence"],
            row["initial_quality"],
            row["final_quality"],
            row["quality_delta"],
            row["confidence_delta"],
            row["woa"],
            row["woe"],
            row["response_time_ms"],
            row["created_at"],
        ])

    output.seek(0)
    filename = f"{subject_id}_experiment_results.csv"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)
