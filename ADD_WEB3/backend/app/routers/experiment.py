from __future__ import annotations

import json
import random

from fastapi import APIRouter, HTTPException

from app.database import get_conn
from app.schemas import PracticeLogIn, RestCompleteIn, TrainingCompleteIn, TrialLogIn, TrialLogOut, TrialOut
from app.services.doe import ACTION_OPTIONS, action_quality, advice_text, build_glucose_story, calculate_woa, condition_display_name
from app.services.media import resolve_media_urls
from app.services.glucose_story import build_glucose_story_from_extended_data

router = APIRouter(prefix="/api/experiment", tags=["experiment"])


def _trial_glucose_sample_index(condition_code: str | None, scenario_type: str, instance_id: int) -> int:
    """Map each experimental condition instance to a fixed glucose sample.

    Latin-square rows only change order; the curve shown for a condition must
    not depend on subject id or trial index. Four samples per scenario cover:
    expert/peer style x instance 1/2.
    """
    code = condition_code or ""
    return {"EV": 0, "PV": 1, "ED": 2, "PD": 3, "P": 0, "Q": 0, "R": 2, "S": 2}.get(code, int(instance_id or 0) % 4)


def _baseline_story_from_file(subject_id: str, trial: dict) -> dict | None:
    sample_index = _trial_glucose_sample_index(
        trial["condition_code"] or trial["condition_id"],
        trial["scenario_type"],
        trial["instance_id"],
    )
    story = build_glucose_story_from_extended_data(trial["scenario_type"], "E", sample_index)
    if not story:
        return None

    baseline_series = story["glucose_series"][:14]
    baseline_minutes = [point["minute"] for point in baseline_series]
    baseline_labels = [point.get("time_label") or point.get("label") for point in baseline_series]
    return {
        **story,
        "profile_key": f"{trial['scenario_type']}_sample_{sample_index}",
        "variant_index": sample_index,
        "glucose_series": baseline_series,
        "glucose_axis": {
            **story["glucose_axis"],
            "max_minutes": max(baseline_minutes),
            "time_marks": baseline_minutes,
            "time_labels": baseline_labels,
        },
        "glucose_events": [{"minute": 0, "label": "", "kind": "decision"}],
        "glucose_sample_index": sample_index,
    }


def _media_lookup_key(scenario_type: str, style: str, media: str) -> str:
    scenario_key = "III_short_hyper" if scenario_type == "short_peak" else "IV_persistent_high_normal"
    media_key = "audio" if media in {"voice", "audio"} else "avatar"
    return f"{scenario_key}__{style}__{media_key}"


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
            "UPDATE subjects SET rest_duration_seconds = COALESCE(rest_duration_seconds, 0) + ?, current_module = 'TRAINING2' WHERE id = ?",
            (payload.rest_duration_seconds, payload.subject_id),
        )
    return {"ok": True}


@router.post("/practice-log")
def log_practice(payload: PracticeLogIn) -> dict:
    with get_conn() as conn:
        subject = conn.execute("SELECT id, sub_group FROM subjects WHERE id = ?", (payload.subject_id,)).fetchone()
        if not subject:
            raise HTTPException(status_code=404, detail="subject not found")
        conn.execute(
            """
            INSERT INTO practice_logs (subject_id, sub_group, stage, action, confidence, response_time_ms)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (payload.subject_id, subject["sub_group"], payload.stage, payload.action, payload.confidence, payload.response_time_ms),
        )
    return {"ok": True}


@router.get("/{subject_id}/next", response_model=TrialOut)
def get_next_trial(subject_id: str) -> TrialOut:
    with get_conn() as conn:
        subject = conn.execute(
            "SELECT id, current_trial_index, training_completed_at, current_module, sub_group FROM subjects WHERE id = ?",
            (subject_id,),
        ).fetchone()
        if not subject:
            raise HTTPException(status_code=404, detail="subject not found")
        if subject["current_module"] not in {"RUNNING", "REST"}:
            raise HTTPException(status_code=409, detail="subject is not in running module")

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
            SELECT trial_index, repetition_no, condition_id, condition_code, condition_order,
                   condition_label, scenario_code, repeat_no, scenario_type, condition_style,
                   condition_media, status
            FROM trial_plans
            WHERE subject_id = ?
            ORDER BY trial_index
            """,
            (subject_id,),
        ).fetchall()

    completed_conditions = [
        t["condition_label"] or condition_display_name(t["scenario_type"], t["condition_style"], t["condition_media"])
        for t in all_trials
        if t["trial_index"] < subject["current_trial_index"]
    ]
    remaining_conditions = [
        {
            "trial_index": t["trial_index"],
            "display_name": t["condition_label"] or condition_display_name(t["scenario_type"], t["condition_style"], t["condition_media"]),
            "repetition": t["repetition_no"],
        }
        for t in all_trials
        if t["trial_index"] > subject["current_trial_index"]
    ]

    glucose_story = _baseline_story_from_file(subject_id, trial)
    if not glucose_story:
        glucose_story = build_glucose_story(trial["scenario_type"], subject_id, trial["global_trial_number"], trial["instance_id"])
        glucose_story["glucose_sample_index"] = None
    glucose_series = glucose_story["glucose_series"]
    action_by_code = {item["code"]: item for item in ACTION_OPTIONS}
    ordered_actions = [action_by_code[code] for code in option_codes]
    media_lookup_key = _media_lookup_key(trial["scenario_type"], trial["condition_style"], trial["condition_media"])
    audio_url, video_url = resolve_media_urls(media_lookup_key, trial["condition_media"])

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
        condition_order=trial["condition_order"],
        condition_label=trial["condition_label"],
        scenario_code=trial["scenario_code"],
        repeat_no=trial["repeat_no"],
        task_type=trial["task_type"],
        condition_display=condition_display_name(trial["scenario_type"], trial["condition_style"], trial["condition_media"]),
        scenario_type=trial["scenario_type"],
        condition_style=trial["condition_style"],
        condition_media=trial["condition_media"],
        instance_id=trial["instance_id"],
        option_order_presented=option_codes,
        glucose_profile_key=trial["glucose_profile_key"],
        glucose_trend_label=trial["glucose_trend_label"],
        glucose_variant_index=glucose_story.get("variant_index", trial["glucose_variant_index"]),
        glucose_sample_index=glucose_story.get("glucose_sample_index"),
        trigger_glucose=glucose_story["trigger_glucose"],
        glucose_30=glucose_story["glucose_30"],
        glucose_60=glucose_story["glucose_60"],
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
            "SELECT current_trial_index, sub_group FROM subjects WHERE id = ?",
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
                subject_id, trial_index, condition_id, condition_code, sub_group, condition_order,
                condition_label, scenario_code, repeat_no, task_type, scenario_type, condition_style,
                condition_media, module_number, trial_number_in_module, global_trial_number, instance_id,
                option_order_presented, glucose_profile_key, glucose_trend_label, glucose_variant_index,
                initial_action, initial_choice_score, initial_confidence, confidence_before,
                advice_shown_at, advice_recommendation, advice_recommendation_score,
                final_action, final_choice_score, final_confidence, confidence_after, response_time_ms,
                trial_duration_seconds, initial_quality, final_quality, quality_delta, confidence_delta,
                delta_confidence, woa, woa_score, woa_null_reason, woe, advice_start_ts, advice_end_ts, final_choice_ts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.subject_id,
                payload.trial_index,
                trial["condition_id"],
                trial["condition_code"] or trial["condition_id"],
                subject["sub_group"],
                trial["condition_order"],
                trial["condition_label"],
                trial["scenario_code"],
                trial["repeat_no"],
                trial["task_type"],
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
                SET current_trial_index = ?, current_module = ?
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


@router.get("/{subject_id}/{trial_index}/glucose-outcome/{action_code}/{sample_index}")
def get_glucose_outcome(subject_id: str, trial_index: int, action_code: str, sample_index: int) -> dict:
    """Load extended glucose data (30 points) for a specific action option.
    
    Args:
        subject_id: Subject ID
        trial_index: Trial index
        action_code: Action code (WALK_1KM, WALK_2KM, RUN_1KM, RUN_2KM, NONE)
        sample_index: Sample index (0-3 for each scenario, only use 8 samples total)
    
    Returns:
        Extended glucose story with 30 data points
    """
    with get_conn() as conn:
        trial = conn.execute(
            "SELECT trial_index, condition_id, condition_code, scenario_type, instance_id FROM trial_plans WHERE subject_id = ? AND trial_index = ?",
            (subject_id, trial_index),
        ).fetchone()
        if not trial:
            raise HTTPException(status_code=404, detail="trial not found")
    
    # Limit client input to the documented range; the server still owns the
    # actual trial-level sample choice so baseline and outcome always match.
    if sample_index < 0 or sample_index > 3:
        raise HTTPException(status_code=400, detail="sample_index must be between 0 and 3")

    scenario_type = trial["scenario_type"]
    sample_index = _trial_glucose_sample_index(trial["condition_code"] or trial["condition_id"], scenario_type, trial["instance_id"])
    
    # Load extended glucose data from file
    glucose_story = build_glucose_story_from_extended_data(scenario_type, action_code, sample_index)
    if not glucose_story:
        raise HTTPException(status_code=404, detail="glucose data not available for this action")
    
    return glucose_story
