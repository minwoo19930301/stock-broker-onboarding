from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Stock Broker Onboarding API"
    app_env: str = "local"
    app_debug: bool = True
    allowed_origins: list[str] = [
        "http://127.0.0.1:4321",
        "http://localhost:4321",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]

    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")


settings = Settings()
