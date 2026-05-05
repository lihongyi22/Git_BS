from __future__ import annotations

import json
import random

from fastapi import APIRouter, HTTPException

from app.database import get_conn
from app.schemas import RestCompleteIn, TrainingCompleteIn, TrialLogIn, TrialLogOut, TrialOut
from app.services.doe import ACTION_OPTIONS, action_quality, advice_text, calculate_woa, condition_display_name
from app.services.media import resolve_media_urls

router = APIRouter(prefix="/api/experiment", tags=["experiment"])


@router.post("/training-complete")
def complete_training(payload: TrainingCompleteIn) -> dict:
    with get_conn() as conn:
        subject = conn.execute("SELECT id FROM subjects WHERE id = ?", (payload.subject_id,)).fetchone()
        if not subject:
            raise HTTPException(status_code=404, detail="subject not found")
        conn.execute(
            """
            UPDATE subjects
            SET training_completed_at = CURRENT_TIMESTAMP,
                current_module = CASE WHEN current_module = 'TRAINING' THEN 'PRE_SURVEY' ELSE current_module END
            WHERE id = ?
            """,
            (payload.subject_id,),
        )
    return {"ok": True}


@router.post("/rest-complete")
def complete_rest(payload: RestCompleteIn) -> dict:
    with get_conn() as conn:
        subject = conn.execute("SELECT id FROM subjects WHERE id = ?", (payload.subject_id,)).fetchone()
        if not subject:
            raise HTTPException(status_code=404, detail="subject not found")
        conn.execute(
            "UPDATE subjects SET rest_duration_seconds = COALESCE(rest_duration_seconds, 0) + ?, current_module = 'RUNNING' WHERE id = ?",
            (payload.rest_duration_seconds, payload.subject_id),
        )
    return {"ok": True}


@router.get("/{subject_id}/next", response_model=TrialOut)
def get_next_trial(subject_id: str) -> TrialOut:
    with get_conn() as conn:
        subject = conn.execute(
            "SELECT id, current_trial_index, training_completed_at FROM subjects WHERE id = ?",
            (subject_id,),
        ).fetchone()
        if not subject:
            raise HTTPException(status_code=404, detail="subject not found")
        if not subject["training_completed_at"]:
            raise HTTPException(status_code=409, detail="training not completed")

        trial = conn.execute(
            """
            SELECT *
            FROM trial_plans
            WHERE subject_id = ? AND trial_index = ?
            """,
            (subject_id, subject["current_trial_index"]),
        ).fetchone()
        if not trial:
            raise HTTPException(status_code=404, detail="no more trials")

        option_order = trial["option_order_presented"]
        if option_order:
            option_codes = json.loads(option_order)
        else:
            option_codes = [item["code"] for item in ACTION_OPTIONS]
            random.SystemRandom().shuffle(option_codes)
            conn.execute(
                """
                UPDATE trial_plans
                SET option_order_presented = ?, trial_started_at = COALESCE(trial_started_at, CURRENT_TIMESTAMP)
                WHERE id = ?
                """,
                (json.dumps(option_codes, ensure_ascii=False), trial["id"]),
            )

        total_trials = conn.execute("SELECT COUNT(*) AS cnt FROM trial_plans WHERE subject_id = ?", (subject_id,)).fetchone()["cnt"]
        all_trials = conn.execute(
            """
            SELECT trial_index, repetition_no, condition_id, condition_code, scenario_type, condition_style, condition_media, status
            FROM trial_plans
            WHERE subject_id = ?
            ORDER BY trial_index
            """,
            (subject_id,),
        ).fetchall()

    completed_conditions = [
        condition_display_name(t["scenario_type"], t["condition_style"], t["condition_media"])
        for t in all_trials
        if t["trial_index"] < subject["current_trial_index"]
    ]
    remaining_conditions = [
        {
            "trial_index": t["trial_index"],
            "display_name": condition_display_name(t["scenario_type"], t["condition_style"], t["condition_media"]),
            "repetition": t["repetition_no"],
        }
        for t in all_trials
        if t["trial_index"] > subject["current_trial_index"]
    ]

    glucose_series = json.loads(trial["glucose_series_json"])
    glucose_story = json.loads(trial["glucose_outcome_json"])
    action_by_code = {item["code"]: item for item in ACTION_OPTIONS}
    ordered_actions = [action_by_code[code] for code in option_codes]
    audio_url, video_url = resolve_media_urls(trial["condition_id"], trial["condition_media"])

    return TrialOut(
        subject_id=subject_id,
        trial_index=trial["trial_index"],
        total_trials=total_trials,
        repetition_no=trial["repetition_no"],
        module_number=trial["module_number"],
        trial_number_in_module=trial["trial_number_in_module"],
        global_trial_number=trial["global_trial_number"],
        condition_id=trial["condition_id"],
        condition_code=trial["condition_code"] or trial["condition_id"],
        condition_display=condition_display_name(trial["scenario_type"], trial["condition_style"], trial["condition_media"]),
        scenario_type=trial["scenario_type"],
        condition_style=trial["condition_style"],
        condition_media=trial["condition_media"],
        instance_id=trial["instance_id"],
        option_order_presented=option_codes,
        glucose_profile_key=trial["glucose_profile_key"],
        glucose_trend_label=trial["glucose_trend_label"],
        glucose_variant_index=trial["glucose_variant_index"],
        trigger_glucose=trial["trigger_glucose"],
        glucose_30=trial["glucose_30"],
        glucose_60=trial["glucose_60"],
        glucose_series=glucose_series,
        glucose_axis=glucose_story["glucose_axis"],
        glucose_events=glucose_story["glucose_events"],
        glucose_outcome_series=glucose_story["glucose_outcome_series"],
        glucose_outcome_summary=glucose_story["glucose_outcome_summary"],
        action_options=ordered_actions,
        recommended_action=trial["recommended_action"],
        advice_text=advice_text(trial["scenario_type"], trial["condition_style"], trial["recommended_action"]),
        audio_url=audio_url,
        video_url=video_url,
        completed_conditions=completed_conditions,
        remaining_conditions=remaining_conditions,
    )


@router.post("/log", response_model=TrialLogOut)
def log_trial(payload: TrialLogIn) -> TrialLogOut:
    with get_conn() as conn:
        subject = conn.execute(
            "SELECT current_trial_index FROM subjects WHERE id = ?",
            (payload.subject_id,),
        ).fetchone()
        if not subject:
            raise HTTPException(status_code=404, detail="subject not found")
        if payload.trial_index != subject["current_trial_index"]:
            raise HTTPException(status_code=409, detail="trial index mismatch")

        trial = conn.execute(
            "SELECT * FROM trial_plans WHERE subject_id = ? AND trial_index = ?",
            (payload.subject_id, payload.trial_index),
        ).fetchone()
        if not trial:
            raise HTTPException(status_code=404, detail="trial not found")

        initial_q = action_quality(trial["scenario_type"], payload.initial_action)
        final_q = action_quality(trial["scenario_type"], payload.final_action)
        advice_q = action_quality(trial["scenario_type"], trial["recommended_action"])
        woa, woa_null_reason = calculate_woa(initial_q, final_q, advice_q)
        confidence_delta = float(payload.final_confidence - payload.initial_confidence)
        quality_delta = float(final_q - initial_q)
        duration_seconds = round(payload.response_time_ms / 1000, 3)

        conn.execute(
            """
            INSERT INTO trial_logs (
                subject_id, trial_index, condition_id, condition_code, scenario_type, condition_style,
                condition_media, module_number, trial_number_in_module, global_trial_number, instance_id,
                option_order_presented, glucose_profile_key, glucose_trend_label, glucose_variant_index,
                initial_action, initial_choice_score, initial_confidence, confidence_before,
                advice_shown_at, advice_recommendation, advice_recommendation_score,
                final_action, final_choice_score, final_confidence, confidence_after, response_time_ms,
                trial_duration_seconds, initial_quality, final_quality, quality_delta, confidence_delta,
                delta_confidence, woa, woa_score, woa_null_reason, woe, advice_start_ts, advice_end_ts, final_choice_ts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.subject_id,
                payload.trial_index,
                trial["condition_id"],
                trial["condition_code"] or trial["condition_id"],
                trial["scenario_type"],
                trial["condition_style"],
                trial["condition_media"],
                trial["module_number"],
                trial["trial_number_in_module"],
                trial["global_trial_number"],
                trial["instance_id"],
                trial["option_order_presented"],
                trial["glucose_profile_key"],
                trial["glucose_trend_label"],
                trial["glucose_variant_index"],
                payload.initial_action,
                initial_q,
                payload.initial_confidence,
                payload.initial_confidence,
                trial["recommended_action"],
                advice_q,
                payload.final_action,
                final_q,
                payload.final_confidence,
                payload.final_confidence,
                payload.response_time_ms,
                duration_seconds,
                initial_q,
                final_q,
                quality_delta,
                confidence_delta,
                confidence_delta,
                woa,
                woa,
                woa_null_reason,
                None if woa is None else round(1.0 - woa, 4),
                payload.advice_start_ts,
                payload.advice_end_ts,
                payload.final_choice_ts,
            ),
        )

        conn.execute("UPDATE trial_plans SET status = 'done' WHERE subject_id = ? AND trial_index = ?", (payload.subject_id, payload.trial_index))
        next_trial = payload.trial_index + 1
        total_trials = conn.execute("SELECT COUNT(*) AS cnt FROM trial_plans WHERE subject_id = ?", (payload.subject_id,)).fetchone()["cnt"]
        rest_required = next_trial == 8
        if next_trial >= total_trials:
            module = "POST_SURVEY"
            conn.execute(
                """
                UPDATE subjects
                SET current_trial_index = ?, current_module = ?, experiment_completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (next_trial, module, payload.subject_id),
            )
        else:
            module = "REST" if rest_required else "RUNNING"
            conn.execute(
                """
                UPDATE subjects
                SET current_trial_index = ?, current_module = ?,
                    experiment_started_at = COALESCE(experiment_started_at, CURRENT_TIMESTAMP),
                    rest_started_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE rest_started_at END
                WHERE id = ?
                """,
                (next_trial, module, rest_required, payload.subject_id),
            )

    return TrialLogOut(
        ok=True,
        next_trial_index=next_trial if next_trial < total_trials else None,
        experiment_complete=next_trial >= total_trials,
        rest_required=rest_required,
        woa=woa,
        woa_null_reason=woa_null_reason,
        confidence_delta=confidence_delta,
        quality_delta=quality_delta,
    )
