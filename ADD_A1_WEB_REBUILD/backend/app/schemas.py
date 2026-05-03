from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Gender = Literal["M", "F", "Other"]
Scenario = Literal["III_short_hyper", "IV_persistent_high_normal"]
Style = Literal["expert", "peer"]
Media = Literal["audio", "avatar"]


class SubjectCreate(BaseModel):
    subject_id: str = Field(min_length=2, max_length=30)
    name: Optional[str] = Field(default=None, max_length=40)
    phone: Optional[str] = Field(default=None, max_length=30)
    national_id: Optional[str] = Field(default=None, max_length=40)
    age: int = Field(ge=18, le=95)
    gender: Gender
    repeat_count: int = Field(default=2, ge=2, le=4)


class SubjectOut(BaseModel):
    subject_id: str
    name: Optional[str]
    phone: Optional[str]
    national_id: Optional[str]
    age: int
    gender: str
    repeat_count: int
    latin_row: int
    total_trials: int
    current_trial_index: int
    current_module: str


class SubjectRecord(BaseModel):
    subject_id: str
    age: int
    gender: str
    repeat_count: int
    current_trial_index: int
    total_trials: int
    created_at: str


class TrialOut(BaseModel):
    subject_id: str
    trial_index: int
    total_trials: int
    repetition_no: int
    condition_id: str
    condition_display: str
    scenario_type: Scenario
    condition_style: Style
    condition_media: Media
    glucose_profile_key: Optional[str] = None
    glucose_trend_label: Optional[str] = None
    glucose_variant_index: Optional[int] = None
    trigger_glucose: float
    glucose_30: float
    glucose_60: float
    glucose_series: list[dict]
    glucose_axis: dict
    glucose_events: list[dict]
    glucose_outcome_series: dict[str, list[dict]]
    glucose_outcome_summary: dict[str, dict]
    action_options: list[dict]
    recommended_action: str
    advice_text: str
    audio_url: Optional[str]
    video_url: Optional[str]
    completed_conditions: list[str]
    remaining_conditions: list[dict]


class TrialLogIn(BaseModel):
    subject_id: str
    trial_index: int
    initial_action: str
    initial_confidence: int = Field(ge=1, le=5)
    final_action: str
    final_confidence: int = Field(ge=1, le=5)
    response_time_ms: int = Field(ge=0, le=180000)
    advice_start_ts: Optional[int] = None
    advice_end_ts: Optional[int] = None
    final_choice_ts: Optional[int] = None


class TrialLogOut(BaseModel):
    ok: bool
    next_trial_index: Optional[int]
    experiment_complete: bool
    woa: Optional[float]
    woe: Optional[float]
    confidence_delta: float
    quality_delta: float


class SurveyIn(BaseModel):
    subject_id: str
    survey_type: Literal["pre", "post", "task"]
    payload: dict


class SurveyRecord(BaseModel):
    id: int
    subject_id: str
    survey_type: str
    payload: dict
    created_at: str


class SurveyOut(BaseModel):
    survey: SurveyRecord


class SurveyListOut(BaseModel):
    surveys: list[SurveyRecord]


class ScaleConfigOut(BaseModel):
    scales: dict


class ScaleConfigIn(BaseModel):
    scales: dict
