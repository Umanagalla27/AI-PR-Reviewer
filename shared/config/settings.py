import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/codereview"
    
    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    # OpenAI
    OPENAI_API_KEY: str = "sk-..."
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # GitHub App
    GITHUB_APP_ID: int = 123456
    GITHUB_APP_PRIVATE_KEY: str = ""
    GITHUB_WEBHOOK_SECRET: str = "your_webhook_secret"
    
    # Service URLs
    WEBHOOK_SERVICE_URL: str = "http://webhook:8001"
    ORCHESTRATOR_URL: str = "http://orchestrator:8002"
    REVIEWER_URL: str = "http://reviewer:8003"
    LEARNER_URL: str = "http://learner:8004"
    
    # Langfuse
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
