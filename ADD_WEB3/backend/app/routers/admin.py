from __future__ import annotations

from fastapi import APIRouter

from app.database import get_conn

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/dashboard")
def dashboard() -> dict:
    with get_conn() as conn:
        completed_total = conn.execute("SELECT COUNT(*) AS cnt FROM subjects WHERE experiment_completed_at IS NOT NULL").fetchone()["cnt"]
        group_rows = conn.execute(
            """
            SELECT group_number, COUNT(*) AS cnt
            FROM subjects
            WHERE experiment_completed_at IS NOT NULL
            GROUP BY group_number
            """
        ).fetchall()
        media_rows = conn.execute("SELECT media_order, COUNT(*) AS cnt FROM subjects GROUP BY media_order").fetchall()
        today_completed = conn.execute(
            "SELECT COUNT(*) AS cnt FROM subjects WHERE date(experiment_completed_at) = date('now', 'localtime')"
        ).fetchone()["cnt"]
        total_trials = conn.execute("SELECT COUNT(*) AS cnt FROM trial_logs").fetchone()["cnt"]
        complete_trials = conn.execute(
            """
            SELECT COUNT(*) AS cnt FROM trial_logs
            WHERE initial_action IS NOT NULL
              AND confidence_before IS NOT NULL
              AND advice_recommendation IS NOT NULL
              AND final_action IS NOT NULL
              AND confidence_after IS NOT NULL
              AND option_order_presented IS NOT NULL
            """
        ).fetchone()["cnt"]
    return {
        "completed_total": completed_total,
        "target_total": 40,
        "groups": {str(i): 0 for i in range(1, 5)} | {str(row["group_number"]): row["cnt"] for row in group_rows},
        "media_order": {"voice_first": 0, "digital_human_first": 0} | {row["media_order"]: row["cnt"] for row in media_rows},
        "today_completed": today_completed,
        "data_integrity_rate": round(complete_trials / total_trials, 4) if total_trials else 1.0,
    }
