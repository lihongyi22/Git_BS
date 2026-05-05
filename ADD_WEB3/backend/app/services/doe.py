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
    scenario = {"short_peak": "短时高血糖", "sustained_high": "持续偏高血糖"}.get(scenario_type, scenario_type)
    style_name = {"expert": "专家建议", "peer": "同伴建议"}.get(style, style)
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
                    "glucose_trend_label": "短时高血糖" if scenario_type == "short_peak" else "持续偏高",
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


def build_glucose_story(scenario_type: str, participant_code: str, trial_number: int, instance_id: int = 1) -> dict:
    if scenario_type == "short_peak":
        base_values = [7.6, 7.8, 8.0, 8.5, 9.7, 10.8, 11.2, 10.7, 9.9, 9.1, 8.5]
    else:
        base_values = [8.1, 8.3, 8.6, 8.9, 9.2, 9.4, 9.5, 9.4, 9.2, 9.0, 8.8]
    seed = f"{participant_code}-{trial_number}-{instance_id}-{scenario_type}"
    rng = random.Random(seed)
    minutes = [-30, -15, 0, 15, 30, 45, 60, 75, 90, 105, 120]
    drift = rng.uniform(-0.18, 0.18)
    base = [
        {
            "minute": minute,
            "value": round(value + drift + rng.uniform(-0.05, 0.05), 2),
            "kind": "decision" if minute == 0 else ("forecast" if minute > 0 else "history"),
            "label": "当前" if minute == 0 else (f"+{minute}min" if minute > 0 else f"{minute}min"),
            "state": "血糖偏高",
        }
        for minute, value in zip(minutes, base_values)
    ]
    outcome_series = {code: _apply_action(base, scenario_type, code) for code in ["A", "B", "C", "D", "E"]}
    return {
        "profile_key": f"{scenario_type}_{instance_id}",
        "trend_label": "短时高血糖" if scenario_type == "short_peak" else "持续偏高",
        "variant_index": instance_id,
        "trigger_glucose": base[2]["value"],
        "glucose_30": base[4]["value"],
        "glucose_60": base[6]["value"],
        "glucose_series": base,
        "glucose_axis": {"min_minutes": -30, "max_minutes": 120, "time_marks": minutes},
        "glucose_events": [{"minute": 0, "label": "当前决策"}],
        "glucose_outcome_series": outcome_series,
        "glucose_outcome_summary": {code: _summary(outcome_series[code]) for code in outcome_series},
    }


def _apply_action(base: list[dict], scenario_type: str, action_code: str) -> list[dict]:
    effects = {
        "short_peak": {"C": -1.25, "A": -0.85, "D": -1.55, "B": -0.45, "E": 0.35},
        "sustained_high": {"B": -0.95, "A": -0.55, "C": -1.20, "D": -1.45, "E": 0.18},
    }[scenario_type][action_code]
    series = []
    for point in base:
        minute = point["minute"]
        if minute <= 0:
            value = point["value"]
            kind = point["kind"]
        else:
            ramp = min(minute / 60, 1.0)
            value = point["value"] + effects * ramp
            kind = "outcome_30" if minute == 30 else ("outcome_60" if minute == 60 else "outcome")
        series.append({**point, "value": round(value, 2), "kind": kind})
    return series


def _summary(series: list[dict]) -> dict:
    by_minute = {p["minute"]: p for p in series}
    g30 = by_minute[30]["value"]
    g60 = by_minute[60]["value"]
    return {
        "minute_30": {"value": g30, "text": _state_text(g30)},
        "minute_60": {"value": g60, "text": _state_text(g60)},
        "summary": "系统基于该运动方案生成的演示性血糖影响预测",
    }


def _state_text(value: float) -> str:
    if value < 3.9:
        return "血糖偏低"
    if value <= 10.0:
        return "血糖处于可接受范围"
    return "血糖偏高"


def action_quality(scenario_type: str, action: str) -> float:
    return EXPERT_SCORES[scenario_type][action]


def calculate_woa(initial_score: float, final_score: float, advice_score: float) -> tuple[float | None, str | None]:
    denominator = advice_score - initial_score
    if abs(denominator) < 1e-9:
        return None, "initial_equals_advice"
    return round((final_score - initial_score) / denominator, 4), None


def advice_text(scenario_type: str, style: str, action: str) -> str:
    action_label = {item["code"]: item["label"] for item in ACTION_OPTIONS}[action]
    scenario = "短时高血糖" if scenario_type == "short_peak" else "持续偏高血糖"
    if style == "expert":
        return f"根据当前{scenario}曲线，建议您选择：{action_label}。"
    return f"如果我遇到这样的{scenario}情况，我会优先考虑：{action_label}。"
