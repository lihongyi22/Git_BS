from __future__ import annotations

import json
from pathlib import Path

DEFAULT_SCALES = {
    "pre": {
        "title": "前测量表",
        "sections": [
            {
                "name": "Stanford慢病自我管理效能（6题，0-10）",
                "items": [
                    "您有多大信心，能够不让疾病带来的疲劳干扰您想做的事情？",
                    "您有多大信心，能够不让疾病带来的身体不适或疼痛干扰您想做的事情？",
                    "您有多大信心，能够不让疾病带来的情绪困扰干扰您想做的事情？",
                    "您有多大信心，能够不让其他症状干扰您想做的事情？",
                    "您有多大信心，能够完成健康管理任务并减少就医需求？",
                    "您有多大信心，能够在服药外采取其他措施降低疾病影响？",
                ],
                "scale": "0-10",
            }
        ],
    },
    "post": {
        "title": "后测量表",
        "sections": [
            {
                "name": "Stanford慢病自我管理效能（6题，0-10）",
                "items": [
                    "您有多大信心，能够不让疾病带来的疲劳干扰您想做的事情？",
                    "您有多大信心，能够不让疾病带来的身体不适或疼痛干扰您想做的事情？",
                    "您有多大信心，能够不让疾病带来的情绪困扰干扰您想做的事情？",
                    "您有多大信心，能够不让其他症状干扰您想做的事情？",
                    "您有多大信心，能够完成健康管理任务并减少就医需求？",
                    "您有多大信心，能够在服药外采取其他措施降低疾病影响？",
                ],
                "scale": "0-10",
            },
            {
                "name": "LLM系统感知（PA1-PA3，1-5）",
                "items": [
                    "我认为这类LLM建议系统对我管理运动和血糖很有帮助。",
                    "总体来说，我对今天体验的LLM建议系统感到满意。",
                    "我相信这个系统给出的运动建议是可靠的。",
                ],
                "scale": "1-5",
            },
        ],
    },
    "task_confidence": {
        "title": "单任务信心量表",
        "scale": "1-5",
        "item": "请评价您当前这个决策的信心程度。",
    },
}


def config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "scales.json"


def load_scales() -> dict:
    path = config_path()
    if not path.exists():
        save_scales(DEFAULT_SCALES)
        return DEFAULT_SCALES
    data = json.loads(path.read_text(encoding="utf-8"))

    merged = json.loads(json.dumps(DEFAULT_SCALES, ensure_ascii=False))
    merged.update({key: value for key, value in data.items() if key in merged})
    for key, value in data.items():
        if key not in merged:
            merged[key] = value

    if merged != data:
        save_scales(merged)

    return merged


def save_scales(scales: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scales, ensure_ascii=False, indent=2), encoding="utf-8")
