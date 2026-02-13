from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    anthropic_api_key: str
    admin_api_key: str
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    fernet_key: str = ""
    default_model: str = "claude-sonnet-4-5-20250929"
    max_agent_iterations: int = 5
    agent_timeout_seconds: int = 30
    resend_api_key: str = ""
    default_from_email: str = "noreply@relayai.com.au"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def override_settings(settings: Settings) -> None:
    """For testing — inject a custom Settings instance."""
    global _settings
    _settings = settings
