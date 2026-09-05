from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Contextual Lexical Graph API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://graph:graph@localhost:5432/lexical_graph"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
