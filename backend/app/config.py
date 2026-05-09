from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file so it works regardless of the working directory
_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # Database
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "smp_user_service"
    db_ro_user: str = "survey_ai_ro"
    db_ro_password: str = ""
    db_rw_user: str = "survey_ai_rw"
    db_rw_password: str = ""

    # LLM - Qwen3 (chat agent)
    qwen3_llm_mux_url: str = "http://8.213.81.219:8002/v1"
    qwen3_llm_mux_api_key: str = ""
    qwen3_model_id: str = "Qwen/Qwen3.6-27B-FP8"

    # LLM - GPT OSS (keyword extraction)
    gpt_oss_llm_url: str = "http://8.213.81.219:8003/v1"
    gpt_oss_model_id: str = "openai/gpt-oss-120b"

    # CORS
    cors_origins: str = "http://localhost:5173"

    # Langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "info"

    # Analytics report pipeline
    nlp_stage1_concurrency: int = 8
    sql_concurrency: int = 4
    llm_summary_concurrency: int = 4
    nlp_batch_size: int = 50
    nlp_batch_min_split: int = 12
    nlp_batch_char_budget: int = 12000
    analytics_synthesis_token_budget: int = 12000
    analytics_orphan_timeout_minutes: int = 15
    gpt_oss_supports_json_mode: bool = False

    @property
    def ro_dsn(self) -> str:
        from urllib.parse import quote_plus
        return (
            f"mysql+aiomysql://{self.db_ro_user}:{quote_plus(self.db_ro_password)}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def rw_dsn(self) -> str:
        from urllib.parse import quote_plus
        return (
            f"mysql+aiomysql://{self.db_rw_user}:{quote_plus(self.db_rw_password)}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
