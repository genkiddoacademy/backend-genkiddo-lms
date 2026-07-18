from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "Genkiddo Internal API"
    DEBUG: bool = False
    
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "genkiddo_db"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DATABASE_URL: str = ""
    
    JWT_SECRET: str = "super-secret-jwt-key-with-at-least-32-characters-long"
    
    WAHA_URL: str = ""
    WAHA_API_KEY: str = ""
    
    ADMIN_EMAIL: str = "admin@genkiddo.com"
    ADMIN_PASSWORD: str = "admin123"
    
    SMTP_HOST: str = "smtp.zoho.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@genkiddo.com"
    SMTP_FROM_NAME: str = "GenKiddo Academy"
    
    NEXT_PUBLIC_INTERNAL_API_KEY: str = "genkiddo-secret-key-123"
    
    GATEWAY_URL: str = "http://localhost:8010"
    GATEWAY_API_KEY: str = "gateway-secret-key-123"
    STORAGE_PATH: str = "storage"
    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"

    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production", "false", "0", "off", "no"}:
                return False
            if normalized in {"true", "1", "on", "yes", "debug", "development", "dev"}:
                return True
        return value
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings():
    """
    Menggunakan lru_cache agar file .env hanya dibaca sekali, 
    tidak dibaca ulang setiap kali settings dipanggil.
    """
    return Settings()

settings = get_settings()
