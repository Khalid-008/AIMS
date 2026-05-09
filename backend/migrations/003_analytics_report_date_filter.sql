-- Adds optional date-range filter columns to survey_analytics_report.
-- The filter is also mixed into input_hash, so different windows naturally
-- produce different cache rows; these columns exist for audit / UI replay.

ALTER TABLE survey_analytics_report
  ADD COLUMN date_from DATE NULL AFTER report_language,
  ADD COLUMN date_to   DATE NULL AFTER date_from;
