-- Adds optional submissions limit column to survey_analytics_report.
-- The limit is mixed into input_hash so different limits produce different
-- cache rows; this column exists for audit / UI replay.

ALTER TABLE survey_analytics_report
  ADD COLUMN submissions_limit INT NULL AFTER date_to;
