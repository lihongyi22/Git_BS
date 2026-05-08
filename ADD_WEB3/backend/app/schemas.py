from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Gender = Literal["M", "F", "Other"]
Scenario = Literal["short_peak", "sustained_high"]
Style = Literal["expert", "peer"]
Media = Literal["voice", "digital_human"]


class SubjectCreate(BaseModel):
    subject_id: Optional[str] = Field(default=None, max_length=30)
    name: Optional[str] = Field(default=None, max_length=40)
    phone: Optional[str] = Field(default=None, max_length=30)
    national_id: Optional[str] = Field(default=None, max_length=40)
    age: int = Field(ge=18, le=95)
    gender: Gender
    sub_group: Optional[Literal["1A", "1B", "2A", "2B"]] = None
    latin_square_row: Optional[int] = Field(default=None, ge=1, le=4)
    media_order: Optional[Literal["voice_first", "digital_human_first"]] = None


class SubjectOut(BaseModel):
    subject_id: str
    participant_code: str
    name: Optional[str]
    phone: Optional[str]
    national_id: Optional[str]
    age: int
    gender: str
    repeat_count: int
    sub_group: str = "1A"
    latin_row: int
    group_number: int
    media_order: str
    training_completed_at: Optional[str] = None
    experiment_started_at: Optional[str] = None
    experiment_completed_at: Optional[str] = None
    rest_duration_seconds: Optional[int] = None
    total_trials: int
    current_trial_index: int
    current_module: str


class SubjectRecord(BaseModel):
    subject_id: str
    participant_code: str
    age: int
    gender: str
    repeat_count: int
    sub_group: str = "1A"
    latin_row: int
    group_number: int
    media_order: str
    training_completed_at: Optional[str] = None
    experiment_completed_at: Optional[str] = None
    current_trial_index: int
    total_trials: int
    created_at: str


class TrialOut(BaseModel):
    subject_id: str
    trial_index: int
    total_trials: int
    repetition_no: int
    module_number: int
    trial_number_in_module: int
    global_trial_number: int
    condition_id: str
    condition_code: str
    condition_order: Optional[int] = None
    condition_label: Optional[str] = None
    scenario_code: Optional[str] = None
    repeat_no: Optional[int] = None
    task_type: str = "formal"
    condition_display: str
    scenario_type: Scenario
    condition_style: Style
    condition_media: Media
    instance_id: int
    option_order_presented: list[str]
    glucose_profile_key: Optional[str] = None
    glucose_trend_label: Optional[str] = None
    glucose_variant_index: Optional[int] = None
    glucose_sample_index: Optional[int] = None
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
    response_time_ms: int = Field(ge=0, le=1800000)
    advice_start_ts: Optional[int] = None
    advice_end_ts: Optional[int] = None
    final_choice_ts: Optional[int] = None


class TrialLogOut(BaseModel):
    ok: bool
    next_trial_index: Optional[int]
    experiment_complete: bool
    rest_required: bool = False
    woa: Optional[float]
    woa_null_reason: Optional[str] = None
    confidence_delta: float
    quality_delta: float


class TrainingCompleteIn(BaseModel):
    subject_id: str


class RestCompleteIn(BaseModel):
    subject_id: str
    rest_duration_seconds: int = Field(ge=0)


class ModuleUpdateIn(BaseModel):
    module: Literal["PRE_SURVEY", "TRAINING1", "PRACTICE1", "RUNNING", "REST", "TRAINING2", "PRACTICE2", "POST_SURVEY", "DONE"]


class PracticeLogIn(BaseModel):
    subject_id: str
    stage: int = Field(ge=1, le=2)
    action: str
    confidence: int = Field(ge=1, le=5)
    response_time_ms: int = Field(ge=0, le=1800000)


class AdminUpdateIn(BaseModel):
    value: str | int
    reason: str = Field(min_length=1, max_length=300)


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
