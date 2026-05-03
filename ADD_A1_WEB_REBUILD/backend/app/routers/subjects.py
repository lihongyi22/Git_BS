from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.database import get_conn
from app.schemas import SubjectCreate, SubjectOut, SubjectRecord
from app.services.doe import assign_latin_row, build_trial_plan

router = APIRouter(prefix="/api/subjects", tags=["subjects"])


@router.post("", response_model=SubjectOut)
def create_subject(payload: SubjectCreate) -> SubjectOut:
    with get_conn() as conn:
        exists = conn.execute("SELECT id FROM subjects WHERE id = ?", (payload.subject_id,)).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="subject_id already exists")

        count_row = conn.execute("SELECT COUNT(*) AS cnt FROM subjects").fetchone()
        latin_row = assign_latin_row(int(count_row["cnt"]))
        plan = build_trial_plan(payload.subject_id, payload.repeat_count, latin_row)

        conn.execute(
            """
            INSERT INTO subjects (id, name, phone, national_id, age, gender, repeat_count, latin_row, current_trial_index, current_module)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'PRE_SURVEY')
            """,
            (
                payload.subject_id,
                payload.name,
                payload.phone,
                payload.national_id,
                payload.age,
                payload.gender,
                payload.repeat_count,
                latin_row,
            ),
        )

        for row in plan:
            conn.execute(
                """
                INSERT INTO trial_plans (
                    subject_id, trial_index, repetition_no, condition_id, scenario_type,
                    condition_style, condition_media, glucose_profile_key, glucose_trend_label, glucose_variant_index,
                    trigger_glucose, glucose_30, glucose_60,
                    glucose_series_json, glucose_outcome_json, recommended_action, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    row["subject_id"],
                    row["trial_index"],
                    row["repetition_no"],
                    row["condition_id"],
                    row["scenario_type"],
                    row["condition_style"],
                    row["condition_media"],
                    row.get("glucose_profile_key"),
                    row.get("glucose_trend_label"),
                    row.get("glucose_variant_index"),
                    row["trigger_glucose"],
                    row["glucose_30"],
                    row["glucose_60"],
                    row["glucose_series_json"],
                    row["glucose_outcome_json"],
                    row["recommended_action"],
                ),
            )

    return SubjectOut(
        subject_id=payload.subject_id,
        name=payload.name,
        phone=payload.phone,
        national_id=payload.national_id,
        age=payload.age,
        gender=payload.gender,
        repeat_count=payload.repeat_count,
        latin_row=latin_row,
        total_trials=len(plan),
        current_trial_index=0,
        current_module="PRE_SURVEY",
    )


@router.get("", response_model=list[SubjectRecord])
def list_subjects() -> list[SubjectRecord]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.age, s.gender, s.repeat_count, s.current_trial_index, s.created_at,
                   (SELECT COUNT(*) FROM trial_plans t WHERE t.subject_id = s.id) AS total_trials
            FROM subjects s
            ORDER BY s.created_at DESC
            """
        ).fetchall()
    return [
        SubjectRecord(
            subject_id=row["id"],
            age=row["age"],
            gender=row["gender"],
            repeat_count=row["repeat_count"],
            current_trial_index=row["current_trial_index"],
            total_trials=row["total_trials"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


@router.get("/{subject_id}", response_model=SubjectOut)
def get_subject(subject_id: str) -> SubjectOut:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, name, phone, national_id, age, gender, repeat_count, latin_row,
                   current_trial_index, current_module
            FROM subjects
            WHERE id = ?
            """,
            (subject_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="subject not found")
        total_trials = conn.execute(
            "SELECT COUNT(*) AS cnt FROM trial_plans WHERE subject_id = ?",
            (subject_id,),
        ).fetchone()["cnt"]

    return SubjectOut(
        subject_id=row["id"],
        name=row["name"],
        phone=row["phone"],
        national_id=row["national_id"],
        age=row["age"],
        gender=row["gender"],
        repeat_count=row["repeat_count"],
        latin_row=row["latin_row"],
        total_trials=total_trials,
        current_trial_index=row["current_trial_index"],
        current_module=row["current_module"],
    )
