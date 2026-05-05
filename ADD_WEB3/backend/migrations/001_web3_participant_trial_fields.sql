ALTER TABLE subjects ADD COLUMN group_number INTEGER NOT NULL DEFAULT 1;
ALTER TABLE subjects ADD COLUMN media_order TEXT NOT NULL DEFAULT 'voice_first';
ALTER TABLE subjects ADD COLUMN training_completed_at TEXT;
ALTER TABLE subjects ADD COLUMN experiment_started_at TEXT;
ALTER TABLE subjects ADD COLUMN experiment_completed_at TEXT;
ALTER TABLE subjects ADD COLUMN rest_started_at TEXT;
ALTER TABLE subjects ADD COLUMN rest_duration_seconds INTEGER;

ALTER TABLE trial_plans ADD COLUMN module_number INTEGER NOT NULL DEFAULT 1;
ALTER TABLE trial_plans ADD COLUMN trial_number_in_module INTEGER NOT NULL DEFAULT 1;
ALTER TABLE trial_plans ADD COLUMN global_trial_number INTEGER NOT NULL DEFAULT 1;
ALTER TABLE trial_plans ADD COLUMN condition_code TEXT NOT NULL DEFAULT '';
ALTER TABLE trial_plans ADD COLUMN instance_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE trial_plans ADD COLUMN option_order_presented TEXT;
ALTER TABLE trial_plans ADD COLUMN trial_started_at TEXT;
