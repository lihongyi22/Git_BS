from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.database import get_conn
from app.schemas import TrialLogIn, TrialLogOut, TrialOut
from app.services.doe import (
    ACTION_OPTIONS,
    build_glucose_story,
    action_quality,
    advice_text,
    calculate_woa_woe,
    condition_display_name,
)
from app.services.media import resolve_media_urls

router = APIRouter(prefix="/api/experiment", tags=["experiment"])


@router.get("/{subject_id}/next", response_model=TrialOut)
def get_next_trial(subject_id: str) -> TrialOut:
    with get_conn() as conn:
        subject = conn.execute(
            "SELECT id, current_trial_index FROM subjects WHERE id = ?",
            (subject_id,),
        ).fetchone()
        if not subject:
            raise HTTPException(status_code=404, detail="subject not found")

        trial = conn.execute(
            """
             SELECT trial_index, repetition_no, condition_id, scenario_type, condition_style, condition_media,
                 glucose_profile_key, glucose_trend_label, glucose_variant_index,
                 trigger_glucose, glucose_30, glucose_60, glucose_series_json, glucose_outcome_json, recommended_action
            FROM trial_plans
            WHERE subject_id = ? AND trial_index = ?
            """,
            (subject_id, subject["current_trial_index"]),
        ).fetchone()
        if not trial:
            raise HTTPException(status_code=404, detail="no more trials")

        total_trials = conn.execute(
            "SELECT COUNT(*) AS cnt FROM trial_plans WHERE subject_id = ?",
            (subject_id,),
        ).fetchone()["cnt"]

        # 获取已完成的条件和待完成的条件
        all_trials = conn.execute(
            """
            SELECT trial_index, repetition_no, condition_id, scenario_type, condition_style, condition_media, status
            FROM trial_plans
            WHERE subject_id = ?
            ORDER BY trial_index
            """,
            (subject_id,),
        ).fetchall()

    completed_conditions = []
    remaining_conditions = []
    current_idx = subject["current_trial_index"]
    
    for t in all_trials:
        display_name = condition_display_name(t["scenario_type"], t["condition_style"], t["condition_media"])
        if t["trial_index"] < current_idx:
            completed_conditions.append(display_name)
        elif t["trial_index"] > current_idx:
            remaining_conditions.append({
                "trial_index": t["trial_index"],
                "display_name": display_name,
                "repetition": t["repetition_no"]
            })

    audio_url, video_url = resolve_media_urls(trial["condition_id"], trial["condition_media"])
    condition_display = condition_display_name(trial["scenario_type"], trial["condition_style"], trial["condition_media"])
    if trial["glucose_series_json"] and trial["glucose_outcome_json"]:
        glucose_series = json.loads(trial["glucose_series_json"])
        glucose_story = json.loads(trial["glucose_outcome_json"])
    else:
        glucose_story = build_glucose_story(trial["scenario_type"], subject_id, trial["trial_index"])
        glucose_series = glucose_story["glucose_series"]

    return TrialOut(
        subject_id=subject_id,
        trial_index=trial["trial_index"],
        total_trials=total_trials,
        repetition_no=trial["repetition_no"],
        condition_id=trial["condition_id"],
        condition_display=condition_display,
        scenario_type=trial["scenario_type"],
        condition_style=trial["condition_style"],
        condition_media=trial["condition_media"],
        glucose_profile_key=trial["glucose_profile_key"],
        glucose_trend_label=trial["glucose_trend_label"],
        glucose_variant_index=trial["glucose_variant_index"],
        trigger_glucose=trial["trigger_glucose"],
        glucose_30=trial["glucose_30"],
        glucose_60=trial["glucose_60"],
        glucose_series=glucose_series,
        glucose_axis=glucose_story["axis"] if "axis" in glucose_story else glucose_story["glucose_axis"],
        glucose_events=glucose_story["events"] if "events" in glucose_story else glucose_story["glucose_events"],
        glucose_outcome_series=glucose_story["outcome_series"] if "outcome_series" in glucose_story else glucose_story["glucose_outcome_series"],
        glucose_outcome_summary=glucose_story["outcome_summary"] if "outcome_summary" in glucose_story else glucose_story["glucose_outcome_summary"],
        action_options=ACTION_OPTIONS,
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
            """
            SELECT trial_index, condition_id, scenario_type, condition_style, condition_media,
                   glucose_profile_key, glucose_trend_label, glucose_variant_index,
                   recommended_action
            FROM trial_plans
            WHERE subject_id = ? AND trial_index = ?
            """,
            (payload.subject_id, payload.trial_index),
        ).fetchone()
        if not trial:
            raise HTTPException(status_code=404, detail="trial not found")

        initial_q = action_quality(trial["scenario_type"], payload.initial_action)
        final_q = action_quality(trial["scenario_type"], payload.final_action)
        advice_q = action_quality(trial["scenario_type"], trial["recommended_action"])
        woa, woe = calculate_woa_woe(initial_q, final_q, advice_q)
        confidence_delta = float(payload.final_confidence - payload.initial_confidence)
        quality_delta = float(final_q - initial_q)

        conn.execute(
            """
            INSERT INTO trial_logs (
                subject_id, trial_index, condition_id, scenario_type, condition_style, condition_media,
                glucose_profile_key, glucose_trend_label, glucose_variant_index,
                initial_action, initial_confidence, final_action, final_confidence, response_time_ms,
                initial_quality, final_quality, quality_delta, confidence_delta, woa, woe,
                advice_start_ts, advice_end_ts, final_choice_ts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.subject_id,
                payload.trial_index,
                trial["condition_id"],
                trial["scenario_type"],
                trial["condition_style"],
                trial["condition_media"],
                trial["glucose_profile_key"],
                trial["glucose_trend_label"],
                trial["glucose_variant_index"],
                payload.initial_action,
                payload.initial_confidence,
                payload.final_action,
                payload.final_confidence,
                payload.response_time_ms,
                initial_q,
                final_q,
                quality_delta,
                confidence_delta,
                woa,
                woe,
                payload.advice_start_ts,
                payload.advice_end_ts,
                payload.final_choice_ts,
            ),
        )

        conn.execute(
            "UPDATE trial_plans SET status = 'done' WHERE subject_id = ? AND trial_index = ?",
            (payload.subject_id, payload.trial_index),
        )

        next_trial = payload.trial_index + 1
        total_trials = conn.execute(
            "SELECT COUNT(*) AS cnt FROM trial_plans WHERE subject_id = ?",
            (payload.subject_id,),
        ).fetchone()["cnt"]
        module = "RUNNING" if next_trial < total_trials else "POST_SURVEY"
        conn.execute(
            "UPDATE subjects SET current_trial_index = ?, current_module = ? WHERE id = ?",
            (next_trial, module, payload.subject_id),
        )

    return TrialLogOut(
        ok=True,
        next_trial_index=next_trial if next_trial < total_trials else None,
        experiment_complete=next_trial >= total_trials,
        woa=woa,
        woe=woe,
        confidence_delta=confidence_delta,
        quality_delta=quality_delta,
    )
