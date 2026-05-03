from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


GLUCOSE_TIMELINE = [-30, -15, 0, 15, 30, 45, 60, 75, 90, 105, 120]

SCENARIO_TEMPLATE_LABELS = {
    "短时高血糖": "III_short_hyper",
    "持续偏高血糖": "IV_persistent_high_normal",
}

ACTION_SUMMARY_RULES = {
    "III_short_hyper": {
        "RUN_1KM": {
            "minute_30": {"text": "血糖正常或偏低", "kind": "range", "base": 7.25, "spread": 0.20},
            "minute_60": {"text": "血糖正常", "kind": "fixed", "base": 7.05, "spread": 0.14},
            "minute_120": {"text": "血糖正常", "kind": "fixed", "base": 6.85, "spread": 0.12},
            "summary": "达到目的，前期可能偏低",
        },
        "RUN_2KM": {
            "minute_30": {"text": "血糖正常", "kind": "fixed", "base": 7.45, "spread": 0.16},
            "minute_60": {"text": "血糖正常或偏低", "kind": "range", "base": 6.95, "spread": 0.18},
            "minute_120": {"text": "血糖正常或偏低", "kind": "range", "base": 6.78, "spread": 0.16},
            "summary": "达到目的，后续可能偏低",
        },
        "WALK_1KM": {
            "minute_30": {"text": "血糖偏高", "kind": "fixed", "base": 8.15, "spread": 0.16},
            "minute_60": {"text": "血糖正常", "kind": "fixed", "base": 7.30, "spread": 0.14},
            "minute_120": {"text": "血糖正常", "kind": "fixed", "base": 7.08, "spread": 0.12},
            "summary": "未达到目的，后续无不良后果",
        },
        "WALK_2KM": {
            "minute_30": {"text": "血糖正常", "kind": "fixed", "base": 7.32, "spread": 0.14},
            "minute_60": {"text": "血糖正常或偏低", "kind": "range", "base": 6.98, "spread": 0.16},
            "minute_120": {"text": "血糖正常或偏低", "kind": "range", "base": 6.72, "spread": 0.14},
            "summary": "未达到目的，后续可能偏低",
        },
        "NONE": {
            "minute_30": {"text": "血糖偏高", "kind": "fixed", "base": 8.95, "spread": 0.18},
            "minute_60": {"text": "血糖偏高", "kind": "fixed", "base": 8.70, "spread": 0.16},
            "minute_120": {"text": "血糖偏高", "kind": "fixed", "base": 8.40, "spread": 0.16},
            "summary": "未达到目的，血糖持续偏高",
        },
    },
    "IV_persistent_high_normal": {
        "WALK_2KM": {
            "minute_30": {"text": "血糖正常", "kind": "fixed", "base": 7.50, "spread": 0.16},
            "minute_60": {"text": "血糖正常", "kind": "fixed", "base": 7.20, "spread": 0.14},
            "minute_120": {"text": "血糖正常", "kind": "fixed", "base": 7.02, "spread": 0.12},
            "summary": "即达到目的，又无不良后果",
        },
        "WALK_1KM": {
            "minute_30": {"text": "血糖正常", "kind": "fixed", "base": 7.60, "spread": 0.16},
            "minute_60": {"text": "血糖正常或偏高", "kind": "range", "base": 8.10, "spread": 0.20},
            "minute_120": {"text": "血糖偏高", "kind": "fixed", "base": 8.38, "spread": 0.18},
            "summary": "达到一半目的，后期可能偏高",
        },
        "RUN_1KM": {
            "minute_30": {"text": "血糖正常或偏低", "kind": "range", "base": 6.95, "spread": 0.18},
            "minute_60": {"text": "血糖正常", "kind": "fixed", "base": 7.08, "spread": 0.14},
            "minute_120": {"text": "血糖正常", "kind": "fixed", "base": 6.98, "spread": 0.12},
            "summary": "达到目的，前期可能偏低",
        },
        "RUN_2KM": {
            "minute_30": {"text": "血糖正常或偏低", "kind": "range", "base": 6.82, "spread": 0.18},
            "minute_60": {"text": "血糖正常或偏低", "kind": "range", "base": 6.92, "spread": 0.16},
            "minute_120": {"text": "血糖正常或偏低", "kind": "range", "base": 6.82, "spread": 0.14},
            "summary": "达到目的，全程可能偏低",
        },
        "NONE": {
            "minute_30": {"text": "血糖偏高", "kind": "fixed", "base": 9.35, "spread": 0.16},
            "minute_60": {"text": "血糖偏高", "kind": "fixed", "base": 9.55, "spread": 0.16},
            "minute_120": {"text": "血糖偏高", "kind": "fixed", "base": 9.35, "spread": 0.14},
            "summary": "未达到目的，后续仍可能偏高",
        },
    },
}


@dataclass(frozen=True)
class ScenarioTemplate:
    scenario_type: str
    trend_label: str
    current_glucose: float
    pred_30: float
    pred_60: float


def _seed_to_float(*parts: str) -> float:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _seed_to_int(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _jitter(*parts: str, amplitude: float = 0.12) -> float:
    return (_seed_to_float(*parts) - 0.5) * 2 * amplitude


def _bounded(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _lerp(start: float, end: float, ratio: float) -> float:
    return start + (end - start) * ratio


def _state_text(value: float) -> str:
    if value < 3.9:
        return "血糖偏低"
    if value <= 7.8:
        return "血糖正常"
    return "血糖偏高"


def _series_point(minute: int, value: float, kind: str, label: str, *, state: str | None = None) -> dict:
    return {
        "minute": minute,
        "value": round(value, 2),
        "kind": kind,
        "label": label,
        "state": state or _state_text(value),
    }


def _template_path() -> Path:
    local = Path(__file__).resolve().parents[2] / "config" / "scenario_templates.csv"
    if local.exists():
        return local
    fallback = Path(__file__).resolve().parents[5] / "WEB_MAIN_PLAT1" / "THESIS_EXPERIMENT_SHINY_V2" / "data" / "scenario_templates.csv"
    return fallback if fallback.exists() else local


@lru_cache(maxsize=1)
def template_bank() -> dict[str, list[ScenarioTemplate]]:
    path = _template_path()
    bank: dict[str, list[ScenarioTemplate]] = {key: [] for key in SCENARIO_TEMPLATE_LABELS.values()}
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                scenario_type = SCENARIO_TEMPLATE_LABELS.get(row["scenario"].strip())
                if not scenario_type:
                    continue
                bank[scenario_type].append(
                    ScenarioTemplate(
                        scenario_type=scenario_type,
                        trend_label=row["trend_label"].strip(),
                        current_glucose=float(row["current_glucose"]),
                        pred_30=float(row["pred_30"]),
                        pred_60=float(row["pred_60"]),
                    )
                )

    if any(bank.values()):
        return bank

    return {
        "III_short_hyper": [
            ScenarioTemplate("III_short_hyper", "餐后快速升高后回落", 7.2, 11.4, 8.1),
            ScenarioTemplate("III_short_hyper", "短时峰值后恢复", 6.8, 10.9, 7.5),
            ScenarioTemplate("III_short_hyper", "短时突升且60分钟回归", 7.4, 11.2, 8.4),
            ScenarioTemplate("III_short_hyper", "短时高风险随后缓解", 6.9, 10.7, 7.9),
        ],
        "IV_persistent_high_normal": [
            ScenarioTemplate("IV_persistent_high_normal", "平缓上升并维持偏高", 7.0, 9.6, 9.8),
            ScenarioTemplate("IV_persistent_high_normal", "边缘偏高持续状态", 6.7, 9.3, 9.5),
            ScenarioTemplate("IV_persistent_high_normal", "无明显峰值但持续偏高", 7.1, 9.8, 9.7),
            ScenarioTemplate("IV_persistent_high_normal", "长期偏高趋势延续", 6.9, 9.5, 9.6),
        ],
    }


def _select_template(scenario_type: str, subject_id: str, trial_index: int) -> tuple[ScenarioTemplate, int]:
    templates = template_bank()[scenario_type]
    if not templates:
        raise ValueError(f"no glucose templates for scenario {scenario_type}")
    variant_index = _seed_to_int("template", scenario_type, subject_id, str(trial_index)) % len(templates)
    return templates[variant_index], variant_index


def _classify_point(minute: int) -> tuple[str, str]:
    if minute == -15:
        return "meal", "进食"
    if minute == 0:
        return "decision", "决策"
    if minute == 30:
        return "outcome_30", "+30min"
    if minute == 60:
        return "outcome_60", "+60min"
    if minute < 0:
        return "history", f"{minute}min"
    return "future", f"+{minute}min"


def _build_anchor_series(
    scenario_type: str,
    subject_id: str,
    trial_index: int,
    template: ScenarioTemplate,
    *,
    action_code: str | None = None,
) -> list[dict]:
    base_shift = _jitter("base", scenario_type, subject_id, str(trial_index), template.trend_label, amplitude=0.08)
    current_glucose = template.current_glucose + base_shift
    template_pred_30 = template.pred_30 + _jitter("pred30", scenario_type, subject_id, str(trial_index), template.trend_label, amplitude=0.10)
    template_pred_60 = template.pred_60 + _jitter("pred60", scenario_type, subject_id, str(trial_index), template.trend_label, amplitude=0.10)

    if action_code is None:
        target_30 = template_pred_30
        target_60 = template_pred_60
        if scenario_type == "III_short_hyper":
            target_120 = _bounded(7.4 + _jitter("tail-short", scenario_type, subject_id, str(trial_index), template.trend_label, amplitude=0.12), 6.7, 7.8)
        else:
            target_120 = _bounded(target_60 - 0.10 + _jitter("tail-long", scenario_type, subject_id, str(trial_index), template.trend_label, amplitude=0.10), 7.0, 9.8)
    else:
        rule = ACTION_SUMMARY_RULES[scenario_type][action_code]
        target_30 = _bounded(rule["minute_30"]["base"] + _jitter("a30", scenario_type, action_code, subject_id, str(trial_index), template.trend_label, amplitude=rule["minute_30"]["spread"]), 3.4, 13.5)
        target_60 = _bounded(rule["minute_60"]["base"] + _jitter("a60", scenario_type, action_code, subject_id, str(trial_index), template.trend_label, amplitude=rule["minute_60"]["spread"]), 3.4, 13.5)
        target_120 = _bounded(rule["minute_120"]["base"] + _jitter("a120", scenario_type, action_code, subject_id, str(trial_index), template.trend_label, amplitude=rule["minute_120"]["spread"]), 3.4, 13.5)

    points_by_minute = {
        -30: current_glucose - (0.32 if scenario_type == "III_short_hyper" else 0.18) + _jitter("m-30", scenario_type, subject_id, str(trial_index), template.trend_label, amplitude=0.06),
        -15: current_glucose - (0.12 if scenario_type == "III_short_hyper" else 0.06) + _jitter("m-15", scenario_type, subject_id, str(trial_index), template.trend_label, amplitude=0.05),
        0: current_glucose,
        15: _lerp(current_glucose, target_30, 0.42) + _jitter("m15", scenario_type, subject_id, str(trial_index), template.trend_label, amplitude=0.05),
        30: target_30,
        45: _lerp(target_30, target_60, 0.52) + _jitter("m45", scenario_type, subject_id, str(trial_index), template.trend_label, amplitude=0.05),
        60: target_60,
        75: _lerp(target_60, target_120, 0.30) + _jitter("m75", scenario_type, subject_id, str(trial_index), template.trend_label, amplitude=0.05),
        90: _lerp(target_60, target_120, 0.55) + _jitter("m90", scenario_type, subject_id, str(trial_index), template.trend_label, amplitude=0.04),
        105: _lerp(target_60, target_120, 0.78) + _jitter("m105", scenario_type, subject_id, str(trial_index), template.trend_label, amplitude=0.04),
        120: target_120,
    }

    series: list[dict] = []
    for minute in GLUCOSE_TIMELINE:
        kind, label = _classify_point(minute)
        series.append(_series_point(minute, points_by_minute[minute], kind, label))
    return series


def _build_summary(scenario_type: str, action_code: str, series: list[dict]) -> dict:
    rule = ACTION_SUMMARY_RULES[scenario_type][action_code]

    def _entry(minute: int, key: str) -> dict:
        marker = rule[key]
        point = next(item for item in series if item["minute"] == minute)
        return {
            "value": point["value"],
            "text": marker["text"],
            "kind": marker["kind"],
        }

    return {
        "minute_30": _entry(30, "minute_30"),
        "minute_60": _entry(60, "minute_60"),
        "minute_120": _entry(120, "minute_120"),
        "summary": rule["summary"],
    }


def build_glucose_story(scenario_type: str, subject_id: str, trial_index: int) -> dict:
    template, variant_index = _select_template(scenario_type, subject_id, trial_index)
    baseline_series = _build_anchor_series(scenario_type, subject_id, trial_index, template)
    action_series: dict[str, list[dict]] = {}
    action_summary: dict[str, dict] = {}

    for action_code in ["WALK_1KM", "WALK_2KM", "RUN_1KM", "RUN_2KM", "NONE"]:
        series = _build_anchor_series(scenario_type, subject_id, trial_index, template, action_code=action_code)
        action_series[action_code] = series
        action_summary[action_code] = _build_summary(scenario_type, action_code, series)

    return {
        "profile_key": f"{scenario_type}::{template.trend_label}::v{variant_index + 1}",
        "trend_label": template.trend_label,
        "variant_index": variant_index + 1,
        "trigger_glucose": baseline_series[2]["value"],
        "glucose_30": baseline_series[4]["value"],
        "glucose_60": baseline_series[6]["value"],
        "glucose_series": baseline_series,
        "glucose_axis": {
            "unit": "mmol/L",
            "step_minutes": 15,
            "window_minutes": 120,
            "min_minutes": -30,
            "max_minutes": 120,
            "time_marks": GLUCOSE_TIMELINE,
        },
        "glucose_events": [
            {"minute": -15, "label": "进食时间点", "kind": "meal"},
            {"minute": 0, "label": "决策时间点", "kind": "decision"},
            {"minute": 30, "label": "+30min", "kind": "outcome_30"},
            {"minute": 60, "label": "+60min", "kind": "outcome_60"},
        ],
        "glucose_outcome_series": action_series,
        "glucose_outcome_summary": action_summary,
    }