from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.services.glucose_story import build_glucose_story as build_glucose_story_v2

ACTION_OPTIONS = [
    {"code": "WALK_1KM", "label": "快走 1km"},
    {"code": "WALK_2KM", "label": "快走 2km"},
    {"code": "RUN_1KM", "label": "慢跑 1km"},
    {"code": "RUN_2KM", "label": "慢跑 2km"},
    {"code": "NONE", "label": "什么都不做"},
]

# 8 conditions = scenario(2) x media(2) x style(2)
BASE_CONDITIONS = [
    ("III_short_hyper", "expert", "audio"),
    ("III_short_hyper", "expert", "avatar"),
    ("III_short_hyper", "peer", "audio"),
    ("III_short_hyper", "peer", "avatar"),
    ("IV_persistent_high_normal", "expert", "audio"),
    ("IV_persistent_high_normal", "expert", "avatar"),
    ("IV_persistent_high_normal", "peer", "audio"),
    ("IV_persistent_high_normal", "peer", "avatar"),
]

LATIN_8 = [
    [0, 1, 2, 3, 4, 5, 6, 7],
    [1, 2, 3, 4, 5, 6, 7, 0],
    [2, 3, 4, 5, 6, 7, 0, 1],
    [3, 4, 5, 6, 7, 0, 1, 2],
    [4, 5, 6, 7, 0, 1, 2, 3],
    [5, 6, 7, 0, 1, 2, 3, 4],
    [6, 7, 0, 1, 2, 3, 4, 5],
    [7, 0, 1, 2, 3, 4, 5, 6],
]

# Higher score = better decision quality.
SCENARIO_SCORE = {
    "III_short_hyper": {
        "RUN_1KM": 100.0,
        "WALK_1KM": 75.0,
        "RUN_2KM": 50.0,
        "WALK_2KM": 25.0,
        "NONE": 0.0,
    },
    "IV_persistent_high_normal": {
        "WALK_2KM": 100.0,
        "WALK_1KM": 75.0,
        "RUN_1KM": 50.0,
        "RUN_2KM": 25.0,
        "NONE": 0.0,
    },
}

RECOMMENDED_ACTION = {
    "III_short_hyper": "RUN_1KM",
    "IV_persistent_high_normal": "WALK_2KM",
}

GLUCOSE_TIMELINE = [-30, -15, 0, 15, 30, 45, 60, 75, 90, 105, 120]

SCENARIO_LABELS = {
    "III_short_hyper": "短时高血糖",
    "IV_persistent_high_normal": "持续偏高血糖",
}

ACTION_PROGRESS_TEXT = {
    "III_short_hyper": {
        "RUN_1KM": {
            "minute_30": "血糖正常或偏低",
            "minute_60": "血糖正常",
            "summary": "达到目的，前期可能偏低",
        },
        "RUN_2KM": {
            "minute_30": "血糖正常",
            "minute_60": "血糖正常或偏低",
            "summary": "达到目的，后续可能偏低",
        },
        "WALK_1KM": {
            "minute_30": "血糖正常",
            "minute_60": "血糖正常",
            "summary": "未达到目的，后续无不良后果",
        },
        "WALK_2KM": {
            "minute_30": "血糖正常",
            "minute_60": "血糖正常或偏低",
            "summary": "未达到目的，后续可能偏低",
        },
        "NONE": {
            "minute_30": "血糖偏高",
            "minute_60": "血糖偏高",
            "summary": "未达到目的，血糖持续偏高",
        },
    },
    "IV_persistent_high_normal": {
        "WALK_2KM": {
            "minute_30": "血糖正常",
            "minute_60": "血糖正常",
            "summary": "即达到目的，又无不良后果",
        },
        "WALK_1KM": {
            "minute_30": "血糖正常",
            "minute_60": "血糖正常或偏高",
            "summary": "达到一半目的，后期可能偏高",
        },
        "RUN_1KM": {
            "minute_30": "血糖正常或偏低",
            "minute_60": "血糖正常",
            "summary": "达到目的，前期可能偏低",
        },
        "RUN_2KM": {
            "minute_30": "血糖正常或偏低",
            "minute_60": "血糖正常或偏低",
            "summary": "达到目的，全程可能偏低",
        },
        "NONE": {
            "minute_30": "血糖偏高",
            "minute_60": "血糖偏高",
            "summary": "未达到目的，后续仍可能偏高",
        },
    },
}

SCENARIO_BASE_SERIES = {
    "III_short_hyper": [8.25, 8.32, 8.42, 8.78, 10.78, 10.34, 8.82, 8.48, 8.22, 8.06, 7.92],
    "IV_persistent_high_normal": [8.15, 8.22, 8.34, 8.56, 9.08, 9.28, 9.18, 8.98, 8.82, 8.74, 8.62],
}

ACTION_ADJUSTMENTS = {
    "III_short_hyper": {
        "RUN_1KM": [0.0, 0.0, 0.0, -0.18, -1.05, -1.38, -1.08, -0.72, -0.42, -0.12, 0.12],
        "RUN_2KM": [0.0, 0.0, 0.0, -0.12, -0.88, -1.58, -1.72, -1.34, -0.98, -0.72, -0.56],
        "WALK_1KM": [0.0, 0.0, 0.0, -0.06, -0.34, -0.56, -0.42, -0.22, -0.04, 0.04, 0.10],
        "WALK_2KM": [0.0, 0.0, 0.0, 0.02, -0.18, -0.22, -0.12, 0.02, 0.14, 0.24, 0.30],
        "NONE": [0.0, 0.0, 0.0, 0.04, 0.22, 0.38, 0.48, 0.50, 0.46, 0.42, 0.38],
    },
    "IV_persistent_high_normal": {
        "WALK_2KM": [0.0, 0.0, 0.0, -0.04, -0.22, -0.50, -0.72, -0.72, -0.64, -0.56, -0.50],
        "WALK_1KM": [0.0, 0.0, 0.0, 0.02, 0.12, 0.18, 0.02, -0.04, -0.06, -0.04, -0.02],
        "RUN_1KM": [0.0, 0.0, 0.0, -0.14, -0.34, -0.78, -1.10, -1.14, -0.98, -0.84, -0.72],
        "RUN_2KM": [0.0, 0.0, 0.0, -0.20, -0.48, -0.96, -1.24, -1.08, -0.90, -0.76, -0.66],
        "NONE": [0.0, 0.0, 0.0, 0.02, 0.10, 0.16, 0.12, 0.08, 0.04, 0.02, 0.00],
    },
}


def _seed_to_float(*parts: str) -> float:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _jitter(*parts: str, amplitude: float = 0.12) -> float:
    return (_seed_to_float(*parts) - 0.5) * 2 * amplitude


def _state_text(value: float) -> str:
    if value < 3.9:
        return "血糖偏低"
    if value <= 7.8:
        return "血糖正常"
    return "血糖偏高"


def _series_point(minute: int, value: float, kind: str, label: str) -> dict:
    return {
        "minute": minute,
        "value": round(value, 2),
        "kind": kind,
        "label": label,
        "state": _state_text(value),
    }


def _base_profile(scenario_type: str, subject_id: str, trial_index: int) -> list[dict]:
    template = SCENARIO_BASE_SERIES[scenario_type]
    drift = _jitter("base", scenario_type, subject_id, str(trial_index), amplitude=0.14)
    points: list[dict] = []
    for minute, base_value in zip(GLUCOSE_TIMELINE, template):
        value = base_value + drift + _jitter("base-point", scenario_type, subject_id, str(trial_index), str(minute), amplitude=0.06)
        if minute == -15:
            kind = "meal"
            label = "进食"
        elif minute == 0:
            kind = "decision"
            label = "决策"
        elif minute < 0:
            kind = "history"
            label = f"{minute}min"
        elif minute in {30, 60}:
            kind = "forecast"
            label = f"+{minute}min"
        else:
            kind = "future"
            label = f"+{minute}min"
        points.append(_series_point(minute, value, kind, label))
    return points


def _action_profile(base_series: list[dict], scenario_type: str, action_code: str, subject_id: str, trial_index: int) -> list[dict]:
    adjustments = ACTION_ADJUSTMENTS[scenario_type][action_code]
    action_series: list[dict] = []
    for point, adjustment in zip(base_series, adjustments):
        minute = int(point["minute"])
        value = float(point["value"]) + adjustment + _jitter("action", scenario_type, action_code, subject_id, str(trial_index), str(minute), amplitude=0.05)
        if minute < 0:
            kind = point["kind"]
            label = point["label"]
        elif minute == 0:
            kind = "decision"
            label = "决策"
        elif minute == 30:
            kind = "outcome_30"
            label = "+30min"
        elif minute == 60:
            kind = "outcome_60"
            label = "+60min"
        else:
            kind = "outcome"
            label = f"+{minute}min"
        action_series.append(_series_point(minute, value, kind, label))
    return action_series


def build_glucose_story(scenario_type: str, subject_id: str, trial_index: int) -> dict:
    return build_glucose_story_v2(scenario_type, subject_id, trial_index)


@dataclass
class ConditionItem:
    scenario_type: str
    style: str
    media: str
    condition_id: str


def assign_latin_row(existing_count: int) -> int:
    return existing_count % 8


def ordered_conditions(latin_row: int) -> list[ConditionItem]:
    indices = LATIN_8[latin_row]
    items: list[ConditionItem] = []
    for idx in indices:
        scenario_type, style, media = BASE_CONDITIONS[idx]
        items.append(
            ConditionItem(
                scenario_type=scenario_type,
                style=style,
                media=media,
                condition_id=f"{scenario_type}__{style}__{media}",
            )
        )
    return items


def build_trial_plan(subject_id: str, repeat_count: int, latin_row: int) -> list[dict]:
    base = ordered_conditions(latin_row)
    plan: list[dict] = []
    trial_index = 0
    for rep in range(1, repeat_count + 1):
        for item in base:
            story = build_glucose_story(item.scenario_type, subject_id, trial_index)
            plan.append(
                {
                    "subject_id": subject_id,
                    "trial_index": trial_index,
                    "repetition_no": rep,
                    "condition_id": item.condition_id,
                    "scenario_type": item.scenario_type,
                    "condition_style": item.style,
                    "condition_media": item.media,
                    "glucose_profile_key": story["profile_key"],
                    "glucose_trend_label": story["trend_label"],
                    "glucose_variant_index": story["variant_index"],
                    "trigger_glucose": story["trigger_glucose"],
                    "glucose_30": story["glucose_30"],
                    "glucose_60": story["glucose_60"],
                    "glucose_series_json": json.dumps(story["glucose_series"], ensure_ascii=False),
                    "glucose_outcome_json": json.dumps({
                        "profile_key": story["profile_key"],
                        "trend_label": story["trend_label"],
                        "variant_index": story["variant_index"],
                        "axis": story["glucose_axis"],
                        "events": story["glucose_events"],
                        "outcome_series": story["glucose_outcome_series"],
                        "outcome_summary": story["glucose_outcome_summary"],
                    }, ensure_ascii=False),
                    "recommended_action": RECOMMENDED_ACTION[item.scenario_type],
                }
            )
            trial_index += 1
    return plan


def generate_glucose_profile(scenario_type: str, subject_id: str, trial_index: int) -> tuple[float, float, float]:
    story = build_glucose_story(scenario_type, subject_id, trial_index)
    return story["trigger_glucose"], story["glucose_30"], story["glucose_60"]


def make_glucose_series(trigger: float, g30: float, g60: float) -> list[dict]:
    series = [
        _series_point(-30, trigger - 0.60, "history", "-30min"),
        _series_point(-15, trigger - 0.28, "meal", "进食"),
        _series_point(0, trigger, "decision", "决策"),
        _series_point(15, (trigger + g30) / 2, "forecast", "+15min"),
        _series_point(30, g30, "forecast", "+30min"),
        _series_point(45, (g30 + g60) / 2, "forecast", "+45min"),
        _series_point(60, g60, "forecast", "+60min"),
        _series_point(75, g60 - 0.18, "future", "+75min"),
        _series_point(90, g60 - 0.30, "future", "+90min"),
        _series_point(105, g60 - 0.36, "future", "+105min"),
        _series_point(120, g60 - 0.42, "future", "+120min"),
    ]
    return series


def condition_display_name(scenario_type: str, style: str, media: str) -> str:
    """生成条件的中文显示名称"""
    scenario_map = {
        "III_short_hyper": "短时高血糖",
        "IV_persistent_high_normal": "持续偏高血糖",
    }
    style_map = {
        "expert": "专家建议",
        "peer": "同伴建议",
    }
    media_map = {
        "audio": "音频",
        "avatar": "视频(数字人)",
    }
    scenario_name = scenario_map.get(scenario_type, scenario_type)
    style_name = style_map.get(style, style)
    media_name = media_map.get(media, media)
    return f"{scenario_name} • {style_name} • {media_name}"


def advice_text(scenario_type: str, style: str, action: str) -> str:
    action_map = {x["code"]: x["label"] for x in ACTION_OPTIONS}
    scenario_name = "短时高血糖" if scenario_type == "III_short_hyper" else "持续偏高血糖"
    action_text = action_map[action]
    if style == "expert":
        return f"您好，我是内分泌科医生。当前属于{scenario_name}，建议您现在执行{action_text}，并在执行后复评血糖变化。"
    return f"我和您一样也在长期控糖。这个{scenario_name}情境下，我更建议您先做{action_text}，通常会更稳一些。"


def action_quality(scenario_type: str, action: str) -> float:
    return SCENARIO_SCORE[scenario_type][action]


def calculate_woa_woe(initial_score: float, final_score: float, advice_score: float) -> tuple[float | None, float | None]:
    denominator = advice_score - initial_score
    if abs(denominator) < 1e-9:
        return None, None
    woa = (final_score - initial_score) / denominator
    woe = 1.0 - woa
    return round(woa, 4), round(woe, 4)
