from __future__ import annotations

import json
import random
import re

ACTION_OPTIONS = [
    {"code": "A", "label": "快走 1 公里"},
    {"code": "B", "label": "快走 2 公里"},
    {"code": "C", "label": "慢跑 1 公里"},
    {"code": "D", "label": "慢跑 2 公里"},
    {"code": "E", "label": "什么都不做"},
]

CONDITION_MAP = {
    "P": {"style_type": "expert", "scenario_type": "short_peak"},
    "Q": {"style_type": "expert", "scenario_type": "sustained_high"},
    "R": {"style_type": "peer", "scenario_type": "short_peak"},
    "S": {"style_type": "peer", "scenario_type": "sustained_high"},
}

LATIN_SQUARE = {
    1: ["P", "Q", "R", "S", "S", "R", "Q", "P"],
    2: ["Q", "R", "S", "P", "P", "S", "R", "Q"],
    3: ["R", "S", "P", "Q", "Q", "P", "S", "R"],
    4: ["S", "P", "Q", "R", "R", "Q", "P", "S"],
}

EXPERT_SCORES = {
    "short_peak": {"C": 100.0, "A": 75.0, "D": 50.0, "B": 25.0, "E": -50.0},
    "sustained_high": {"B": 100.0, "A": 75.0, "C": 50.0, "D": 25.0, "E": -50.0},
}

RECOMMENDED_ACTION = {
    "short_peak": "C",
    "sustained_high": "B",
}


def participant_number(participant_code: str) -> int | None:
    match = re.search(r"(\d+)$", participant_code or "")
    return int(match.group(1)) if match else None


def media_order_for_code(participant_code: str) -> str:
    number = participant_number(participant_code)
    if number is not None and number % 2 == 0:
        return "digital_human_first"
    return "voice_first"


def media_for_module(media_order: str, module_number: int) -> str:
    if media_order == "digital_human_first":
        return "digital_human" if module_number == 1 else "voice"
    return "voice" if module_number == 1 else "digital_human"


def recommend_latin_row(group_counts: dict[int, int]) -> int:
    return min([1, 2, 3, 4], key=lambda row: (group_counts.get(row, 0), row))


def condition_display_name(scenario_type: str, style: str, media: str) -> str:
    scenario = {"short_peak": "短时偏高", "sustained_high": "持续偏高"}.get(scenario_type, scenario_type)
    style_name = {"expert": "专家建议", "peer": "伙伴建议"}.get(style, style)
    media_name = {"voice": "语音", "digital_human": "数字人"}.get(media, media)
    return f"{scenario} - {style_name} - {media_name}"


def build_trial_plan(participant_code: str, latin_square_row: int, media_order: str) -> list[dict]:
    plan: list[dict] = []
    for module_number in [1, 2]:
        media_type = media_for_module(media_order, module_number)
        instance_id = module_number
        for idx, condition_code in enumerate(LATIN_SQUARE[latin_square_row], start=1):
            global_trial_number = (module_number - 1) * 8 + idx
            condition = CONDITION_MAP[condition_code]
            scenario_type = condition["scenario_type"]
            story = build_glucose_story(scenario_type, participant_code, global_trial_number, instance_id)
            plan.append(
                {
                    "subject_id": participant_code,
                    "trial_index": global_trial_number - 1,
                    "repetition_no": module_number,
                    "module_number": module_number,
                    "trial_number_in_module": idx,
                    "global_trial_number": global_trial_number,
                    "condition_id": condition_code,
                    "condition_code": condition_code,
                    "scenario_type": scenario_type,
                    "condition_style": condition["style_type"],
                    "condition_media": media_type,
                    "instance_id": instance_id,
                    "glucose_profile_key": f"{scenario_type}_{instance_id}",
                    "glucose_trend_label": "短时偏高" if scenario_type == "short_peak" else "持续偏高",
                    "glucose_variant_index": instance_id,
                    "trigger_glucose": story["trigger_glucose"],
                    "glucose_30": story["glucose_30"],
                    "glucose_60": story["glucose_60"],
                    "glucose_series_json": json.dumps(story["glucose_series"], ensure_ascii=False),
                    "glucose_outcome_json": json.dumps(story, ensure_ascii=False),
                    "recommended_action": RECOMMENDED_ACTION[scenario_type],
                }
            )
    return plan


def _clock_label(minute: int) -> str:
    base_hour = 14
    base_minute = 0
    total = base_hour * 60 + base_minute + minute
    total %= 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


def build_glucose_story(scenario_type: str, participant_code: str, trial_number: int, instance_id: int = 1) -> dict:
    seed = f"{participant_code}-{trial_number}-{instance_id}-{scenario_type}"
    rng = random.Random(seed)
    minutes = [-45, -40, -35, -30, -25, -20, -15, -10, -5, 0, 15, 30, 45, 60]
    drift = rng.uniform(-0.16, 0.16)
    if scenario_type == "short_peak":
        history_targets = [7.15, 7.25, 7.38, 7.55, 7.76, 8.05, 8.38, 8.72, 8.98, 9.18]
        future_targets = [9.55, 10.15, 9.55, 8.95]
    else:
        history_targets = [8.04, 8.10, 8.18, 8.28, 8.39, 8.50, 8.62, 8.74, 8.86, 8.96]
        future_targets = [8.98, 9.18, 9.10, 8.98]

    base: list[dict] = []
    for idx, minute in enumerate(minutes[:10]):
        value = round(history_targets[idx] + drift + rng.uniform(-0.04, 0.04), 2)
        base.append(
            {
                "minute": minute,
                "value": value,
                "kind": "decision" if idx == 9 else "history",
                "label": _clock_label(minute),
                "time_label": _clock_label(minute),
                "state": _state_text(value),
            }
        )
    for idx, minute in enumerate(minutes[10:]):
        value = round(future_targets[idx] + drift + rng.uniform(-0.06, 0.06), 2)
        base.append(
            {
                "minute": minute,
                "value": value,
                "kind": "forecast",
                "label": _clock_label(minute),
                "time_label": _clock_label(minute),
                "state": _state_text(value),
            }
        )

    outcome_series = {code: _apply_action(base, scenario_type, code) for code in ["A", "B", "C", "D", "E"]}
    return {
        "profile_key": f"{scenario_type}_{instance_id}",
        "trend_label": "短时偏高" if scenario_type == "short_peak" else "持续偏高",
        "variant_index": instance_id,
        "trigger_glucose": base[9]["value"],
        "glucose_30": base[11]["value"],
        "glucose_60": base[13]["value"],
        "glucose_series": base,
        "glucose_axis": {
            "min_minutes": -45,
            "max_minutes": 60,
            "time_marks": minutes,
            "time_labels": [_clock_label(minute) for minute in minutes],
            "decision_minute": 0,
        },
        "glucose_events": [{"minute": 0, "label": "", "kind": "decision"}],
        "glucose_outcome_series": outcome_series,
        "glucose_outcome_summary": {code: _summary(outcome_series[code]) for code in outcome_series},
    }


def _apply_action(base: list[dict], scenario_type: str, action_code: str) -> list[dict]:
    effects = {
        "short_peak": {"C": -1.25, "A": -0.85, "D": -1.55, "B": -0.45, "E": 0.35},
        "sustained_high": {"B": -0.95, "A": -0.55, "C": -1.20, "D": -1.45, "E": 0.18},
    }[scenario_type][action_code]
    target_30 = next(point["value"] for point in base if point["minute"] == 30) + effects * 0.12
    target_60 = next(point["value"] for point in base if point["minute"] == 60) + effects
    series = []
    for point in base:
        minute = point["minute"]
        if minute <= 0:
            value = point["value"]
            kind = point["kind"]
        else:
            if minute == 15:
                value = point["value"] + effects * 0.08
            elif minute == 30:
                value = target_30
            elif minute == 45:
                value = target_30 + (target_60 - target_30) * 0.5
            else:
                value = target_60
            kind = "forecast"
        series.append({**point, "value": round(value, 2), "kind": kind})
    return series


def _summary(series: list[dict]) -> dict:
    return {
        "minute_30": {"value": next(item["value"] for item in series if item["minute"] == 30), "kind": "forecast"},
        "minute_60": {"value": next(item["value"] for item in series if item["minute"] == 60), "kind": "forecast"},
        "summary": "",
    }


def _state_text(value: float) -> str:
    if value < 3.9:
        return "血糖偏低"
    if value <= 10.0:
        return "血糖可接受"
    return "血糖偏高"


def action_quality(scenario_type: str, action: str) -> float:
    return EXPERT_SCORES[scenario_type][action]


def calculate_woa(initial_score: float, final_score: float, advice_score: float) -> tuple[float | None, str | None]:
    denominator = advice_score - initial_score
    if abs(denominator) < 1e-9:
        return None, "initial_equals_advice"
    return round((final_score - initial_score) / denominator, 4), None


def advice_text(scenario_type: str, style: str, action: str) -> str:
    if scenario_type == "short_peak" and style == "expert":
        return "您30分钟内血糖有偏高风险，建议现在慢跑1公里，可有效促进血糖代谢。请尽快执行。"
    if scenario_type == "short_peak" and style == "peer":
        return "我血糖突然高的时候，一般就是，慢跑个1公里，效果挺稳的，你也试试，注意安全，啊。"
    if scenario_type == "sustained_high" and style == "expert":
        return "您血糖预计60分钟内持续偏高，建议现在快走两公里，可有效促进血糖代谢。请尽快执行。"
    return "我血糖一直偏高的时候，一般就是，快走个两公里，走完就稳了。你也试试，注意安全，啊。"
