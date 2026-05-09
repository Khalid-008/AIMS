-- Run against the survey DB with an admin user.
-- Grant the RO user read access to survey tables and RW user CRUD on ai_chat_* only.

CREATE TABLE IF NOT EXISTS ai_chat_session (
  id         BIGINT AUTO_INCREMENT PRIMARY KEY,
  survey_number VARCHAR(64) NOT NULL,
  user_id    VARCHAR(64) NOT NULL,
  created_at DATETIME    NOT NULL,
  INDEX idx_user_survey (user_id, survey_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ai_chat_message (
  id         BIGINT AUTO_INCREMENT PRIMARY KEY,
  session_id BIGINT       NOT NULL,
  role       ENUM('user','assistant','tool') NOT NULL,
  content    MEDIUMTEXT   NOT NULL,
  tool_name  VARCHAR(64)  NULL,
  tool_args  JSON         NULL,
  language   CHAR(2)      NULL,
  created_at DATETIME     NOT NULL,
  CONSTRAINT fk_msg_session FOREIGN KEY (session_id) REFERENCES ai_chat_session(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Grants (adjust DB name and user/host as needed)
-- GRANT SELECT ON smp_user_service.survey              TO 'survey_ai_ro'@'%';
-- GRANT SELECT ON smp_user_service.survey_question     TO 'survey_ai_ro'@'%';
-- GRANT SELECT ON smp_user_service.survey_answer       TO 'survey_ai_ro'@'%';
-- GRANT SELECT ON smp_user_service.survey_answer_option TO 'survey_ai_ro'@'%';
-- GRANT SELECT ON smp_user_service.question_option     TO 'survey_ai_ro'@'%';
-- GRANT SELECT ON smp_user_service.question_dropdown   TO 'survey_ai_ro'@'%';

-- GRANT SELECT, INSERT, UPDATE, DELETE ON smp_user_service.ai_chat_session TO 'survey_ai_rw'@'%';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON smp_user_service.ai_chat_message TO 'survey_ai_rw'@'%';
