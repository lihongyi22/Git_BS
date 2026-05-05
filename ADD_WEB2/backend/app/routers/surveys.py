from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.database import get_conn
from app.schemas import SurveyIn, SurveyListOut, SurveyRecord

router = APIRouter(prefix="/api/surveys", tags=["surveys"])


@router.post("")
def submit_survey(payload: SurveyIn) -> dict:
    with get_conn() as conn:
        subject = conn.execute("SELECT id FROM subjects WHERE id = ?", (payload.subject_id,)).fetchone()
        if not subject:
            raise HTTPException(status_code=404, detail="subject not found")

        conn.execute(
            "INSERT INTO surveys (subject_id, survey_type, payload) VALUES (?, ?, ?)",
            (payload.subject_id, payload.survey_type, json.dumps(payload.payload, ensure_ascii=False)),
        )

        if payload.survey_type == "pre":
            conn.execute(
                "UPDATE subjects SET current_module = 'RUNNING' WHERE id = ?",
                (payload.subject_id,),
            )
        elif payload.survey_type == "post":
            conn.execute(
                "UPDATE subjects SET current_module = 'DONE' WHERE id = ?",
                (payload.subject_id,),
            )

    return {"ok": True}


@router.get("", response_model=SurveyListOut)
def list_surveys() -> SurveyListOut:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, subject_id, survey_type, payload, created_at
            FROM surveys
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
    surveys = [
        SurveyRecord(
            id=row["id"],
            subject_id=row["subject_id"],
            survey_type=row["survey_type"],
            payload=json.loads(row["payload"]),
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return SurveyListOut(surveys=surveys)


@router.get("/{subject_id}", response_model=SurveyListOut)
def list_subject_surveys(subject_id: str) -> SurveyListOut:
    with get_conn() as conn:
        subject = conn.execute("SELECT id FROM subjects WHERE id = ?", (subject_id,)).fetchone()
        if not subject:
            raise HTTPException(status_code=404, detail="subject not found")
        rows = conn.execute(
            """
            SELECT id, subject_id, survey_type, payload, created_at
            FROM surveys
            WHERE subject_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (subject_id,),
        ).fetchall()
    surveys = [
        SurveyRecord(
            id=row["id"],
            subject_id=row["subject_id"],
            survey_type=row["survey_type"],
            payload=json.loads(row["payload"]),
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return SurveyListOut(surveys=surveys)
