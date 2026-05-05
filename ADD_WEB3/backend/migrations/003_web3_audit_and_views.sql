CREATE TABLE IF NOT EXISTS audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    participant_id TEXT NOT NULL,
    changed_by TEXT NOT NULL DEFAULT 'admin',
    change_type TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    reason TEXT NOT NULL
);

DROP VIEW IF EXISTS participant;
CREATE VIEW participant AS
SELECT
    id AS participant_id,
    id AS participant_code,
    group_number,
    media_order,
    latin_row AS latin_square_row,
    training_completed_at,
    experiment_started_at,
    experiment_completed_at,
    created_at
FROM subjects;

DROP VIEW IF EXISTS trial;
CREATE VIEW trial AS
SELECT
    id AS trial_id,
    subject_id AS participant_id,
    module_number,
    trial_number_in_module,
    global_trial_number,
    condition_code,
    scenario_type,
    condition_style AS style_type,
    condition_media AS media_type,
    instance_id,
    option_order_presented,
    initial_action AS initial_choice,
    initial_choice_score,
    confidence_before,
    advice_shown_at,
    advice_recommendation,
    advice_recommendation_score,
    final_action AS final_choice,
    final_choice_score,
    confidence_after,
    woa_score,
    woa_null_reason,
    delta_confidence,
    created_at AS trial_completed_at,
    trial_duration_seconds
FROM trial_logs;
