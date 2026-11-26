from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres"
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_jwt_secret: str = ""
    supabase_service_role_key: str = ""
    jwt_audience: str = "authenticated"
    owner_subject: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    app_timezone: str = "America/Fortaleza"
    log_level: str = "INFO"
    # Em produção a documentação interativa (/docs, /openapi.json) fica desligada.
    docs_enabled: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def jwks_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
