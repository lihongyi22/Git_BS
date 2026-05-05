from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.database import get_conn
from app.schemas import AdminUpdateIn, SubjectCreate, SubjectOut, SubjectRecord
from app.services.doe import build_trial_plan, media_order_for_code, recommend_latin_row

router = APIRouter(prefix="/api/subjects", tags=["subjects"])


def _next_participant_code(conn) -> str:
    rows = conn.execute("SELECT id FROM subjects WHERE id LIKE 'P%'").fetchall()
    max_no = 0
    for row in rows:
        try:
            max_no = max(max_no, int(row["id"][1:]))
        except ValueError:
            continue
    return f"P{max_no + 1:03d}"


def _group_counts(conn) -> dict[int, int]:
    rows = conn.execute("SELECT group_number, COUNT(*) AS cnt FROM subjects GROUP BY group_number").fetchall()
    return {int(row["group_number"]): int(row["cnt"]) for row in rows}


def _subject_out(conn, subject_id: str) -> SubjectOut:
    row = conn.execute(
        """
        SELECT id, name, phone, national_id, age, gender, repeat_count, latin_row, group_number,
               media_order, training_completed_at, experiment_started_at, experiment_completed_at,
               rest_duration_seconds, current_trial_index, current_module
        FROM subjects WHERE id = ?
        """,
        (subject_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="subject not found")
    total_trials = conn.execute("SELECT COUNT(*) AS cnt FROM trial_plans WHERE subject_id = ?", (subject_id,)).fetchone()["cnt"]
    return SubjectOut(
        subject_id=row["id"],
        participant_code=row["id"],
        name=row["name"],
        phone=row["phone"],
        national_id=row["national_id"],
        age=row["age"],
        gender=row["gender"],
        repeat_count=row["repeat_count"],
        latin_row=row["latin_row"],
        group_number=row["group_number"],
        media_order=row["media_order"],
        training_completed_at=row["training_completed_at"],
        experiment_started_at=row["experiment_started_at"],
        experiment_completed_at=row["experiment_completed_at"],
        rest_duration_seconds=row["rest_duration_seconds"],
        total_trials=total_trials,
        current_trial_index=row["current_trial_index"],
        current_module=row["current_module"],
    )


def _replace_plan(conn, subject_id: str, latin_row: int, media_order: str, keep_done: bool = True) -> None:
    done_rows = []
    if keep_done:
        done_rows = conn.execute(
            "SELECT trial_index FROM trial_plans WHERE subject_id = ? AND status = 'done'",
            (subject_id,),
        ).fetchall()
    done_indices = {row["trial_index"] for row in done_rows}
    conn.execute("DELETE FROM trial_plans WHERE subject_id = ? AND status != 'done'", (subject_id,))
    plan = build_trial_plan(subject_id, latin_row, media_order)
    for row in plan:
        if row["trial_index"] in done_indices:
            continue
        conn.execute(
            """
            INSERT INTO trial_plans (
                subject_id, trial_index, repetition_no, module_number, trial_number_in_module,
                global_trial_number, condition_id, condition_code, scenario_type, condition_style,
                condition_media, instance_id, glucose_profile_key, glucose_trend_label,
                glucose_variant_index, trigger_glucose, glucose_30, glucose_60,
                glucose_series_json, glucose_outcome_json, recommended_action, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                row["subject_id"],
                row["trial_index"],
                row["repetition_no"],
                row["module_number"],
                row["trial_number_in_module"],
                row["global_trial_number"],
                row["condition_id"],
                row["condition_code"],
                row["scenario_type"],
                row["condition_style"],
                row["condition_media"],
                row["instance_id"],
                row["glucose_profile_key"],
                row["glucose_trend_label"],
                row["glucose_variant_index"],
                row["trigger_glucose"],
                row["glucose_30"],
                row["glucose_60"],
                row["glucose_series_json"],
                row["glucose_outcome_json"],
                row["recommended_action"],
            ),
        )


@router.post("", response_model=SubjectOut)
def create_subject(payload: SubjectCreate) -> SubjectOut:
    with get_conn() as conn:
        subject_id = payload.subject_id or _next_participant_code(conn)
        exists = conn.execute("SELECT id FROM subjects WHERE id = ?", (subject_id,)).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="subject_id already exists")

        latin_row = payload.latin_square_row or recommend_latin_row(_group_counts(conn))
        media_order = payload.media_order or media_order_for_code(subject_id)
        conn.execute(
            """
            INSERT INTO subjects (
                id, name, phone, national_id, age, gender, repeat_count, latin_row, group_number,
                media_order, current_trial_index, current_module
            ) VALUES (?, ?, ?, ?, ?, ?, 2, ?, ?, ?, 0, 'TRAINING')
            """,
            (
                subject_id,
                payload.name,
                payload.phone,
                payload.national_id,
                payload.age,
                payload.gender,
                latin_row,
                latin_row,
                media_order,
            ),
        )
        _replace_plan(conn, subject_id, latin_row, media_order, keep_done=False)
        return _subject_out(conn, subject_id)


@router.get("", response_model=list[SubjectRecord])
def list_subjects() -> list[SubjectRecord]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.age, s.gender, s.repeat_count, s.latin_row, s.group_number, s.media_order,
                   s.training_completed_at, s.experiment_completed_at, s.current_trial_index, s.created_at,
                   (SELECT COUNT(*) FROM trial_plans t WHERE t.subject_id = s.id) AS total_trials
            FROM subjects s
            ORDER BY s.created_at DESC
            """
        ).fetchall()
    return [
        SubjectRecord(
            subject_id=row["id"],
            participant_code=row["id"],
            age=row["age"],
            gender=row["gender"],
            repeat_count=row["repeat_count"],
            latin_row=row["latin_row"],
            group_number=row["group_number"],
            media_order=row["media_order"],
            training_completed_at=row["training_completed_at"],
            experiment_completed_at=row["experiment_completed_at"],
            current_trial_index=row["current_trial_index"],
            total_trials=row["total_trials"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


@router.get("/{subject_id}", response_model=SubjectOut)
def get_subject(subject_id: str) -> SubjectOut:
    with get_conn() as conn:
        return _subject_out(conn, subject_id)


@router.get("/{subject_id}/sequence")
def get_sequence(subject_id: str) -> dict:
    with get_conn() as conn:
        subject = _subject_out(conn, subject_id)
        rows = conn.execute(
            """
            SELECT trial_index, module_number, condition_code, scenario_type, condition_style,
                   condition_media, instance_id, status
            FROM trial_plans
            WHERE subject_id = ?
            ORDER BY trial_index
            """,
            (subject_id,),
        ).fetchall()
    return {
        "subject_id": subject_id,
        "current_trial_index": subject.current_trial_index,
        "rows": [
            {
                "round": row["trial_index"] + 1,
                "module": row["module_number"],
                "condition_code": row["condition_code"] or row["condition_id"],
                "scenario_type": row["scenario_type"],
                "style_type": row["condition_style"],
                "media_type": row["condition_media"],
                "instance_id": row["instance_id"],
                "status": "已完成" if row["status"] == "done" else ("当前" if row["trial_index"] == subject.current_trial_index else "待完成"),
            }
            for row in rows
        ],
    }


@router.post("/{subject_id}/admin/latin-square")
def update_latin_square(subject_id: str, payload: AdminUpdateIn) -> dict:
    new_value = int(payload.value)
    if new_value not in [1, 2, 3, 4]:
        raise HTTPException(status_code=422, detail="latin square row must be 1-4")
    with get_conn() as conn:
        subject = _subject_out(conn, subject_id)
        conn.execute(
            "UPDATE subjects SET latin_row = ?, group_number = ? WHERE id = ?",
            (new_value, new_value, subject_id),
        )
        _replace_plan(conn, subject_id, new_value, subject.media_order, keep_done=True)
        conn.execute(
            """
            INSERT INTO audit_log (participant_id, change_type, old_value, new_value, reason)
            VALUES (?, 'latin_square_row', ?, ?, ?)
            """,
            (subject_id, str(subject.latin_row), str(new_value), payload.reason),
        )
    return {"ok": True}


@router.post("/{subject_id}/admin/media-order")
def update_media_order(subject_id: str, payload: AdminUpdateIn) -> dict:
    new_value = str(payload.value)
    if new_value not in ["voice_first", "digital_human_first"]:
        raise HTTPException(status_code=422, detail="media_order must be voice_first or digital_human_first")
    with get_conn() as conn:
        subject = _subject_out(conn, subject_id)
        conn.execute("UPDATE subjects SET media_order = ? WHERE id = ?", (new_value, subject_id))
        _replace_plan(conn, subject_id, subject.latin_row, new_value, keep_done=True)
        conn.execute(
            """
            INSERT INTO audit_log (participant_id, change_type, old_value, new_value, reason)
            VALUES (?, 'media_order', ?, ?, ?)
            """,
            (subject_id, subject.media_order, new_value, payload.reason),
        )
    return {"ok": True}


@router.post("/{subject_id}/admin/current-trial")
def update_current_trial(subject_id: str, payload: AdminUpdateIn) -> dict:
    value = int(payload.value)
    if value < 1 or value > 16:
        raise HTTPException(status_code=422, detail="current trial must be 1-16")
    with get_conn() as conn:
        subject = _subject_out(conn, subject_id)
        conn.execute("UPDATE subjects SET current_trial_index = ?, current_module = 'RUNNING' WHERE id = ?", (value - 1, subject_id))
        conn.execute(
            """
            INSERT INTO audit_log (participant_id, change_type, old_value, new_value, reason)
            VALUES (?, 'current_trial', ?, ?, ?)
            """,
            (subject_id, str(subject.current_trial_index + 1), str(value), payload.reason),
        )
    return {"ok": True, "message": f"已将进度设置为第{value}轮，下次将从该轮开始"}


@router.get("/{subject_id}/audit")
def get_audit_log(subject_id: str) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE participant_id = ? ORDER BY changed_at DESC",
            (subject_id,),
        ).fetchall()
    return {"logs": [dict(row) for row in rows]}
