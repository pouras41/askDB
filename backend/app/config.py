from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    jwt_secret: str = "dev-only-change-me-please-use-32-plus-characters"
    access_token_minutes: int = 30
    refresh_token_days: int = 14
    database_url: str = "postgresql+psycopg://askdb:askdb_local_password@localhost:5432/askdb"
    demo_database_url: str = "postgresql+psycopg://demo_reader:demo_reader_pass@localhost:5432/demo"
    upload_dir: str = "data/uploads"
    max_upload_bytes: int = 20 * 1024 * 1024
    max_rows: int = 500
    query_rate_limit: int = 8
    query_rate_window_seconds: int = 60
    query_daily_limit: int = 40
    login_rate_limit: int = 8
    register_rate_limit: int = 5
    auth_rate_window_seconds: int = 60


settings = Settings()
