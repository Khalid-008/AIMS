-- Run against the survey DB with an admin user.
-- Stores executive analytics reports keyed by content-addressed input hash.

CREATE TABLE IF NOT EXISTS survey_analytics_report (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  survey_number   VARCHAR(64)  NOT NULL,
  report_language CHAR(2)      NOT NULL,
  input_hash      CHAR(64)     NOT NULL,
  max_answer_id   BIGINT       NOT NULL,
  answer_count    INT          NOT NULL,
  status          ENUM('pending','running','done','failed','empty') NOT NULL,
  payload_json    LONGTEXT     NULL,
  error_message   TEXT         NULL,
  llm_calls       INT          NOT NULL DEFAULT 0,
  duration_ms     INT          NULL,
  created_at      DATETIME     NOT NULL,
  updated_at      DATETIME     NOT NULL,
  KEY idx_survey  (survey_number),
  KEY idx_hash_status (input_hash, status),
  KEY idx_status_created (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- GRANT SELECT, INSERT, UPDATE ON smp_user_service.survey_analytics_report TO 'survey_ai_rw'@'%';
