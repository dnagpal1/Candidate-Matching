import os
from functools import lru_cache
from typing import List, Optional
from urllib.parse import quote_plus

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""
    
    # API settings
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    debug: bool = Field(default=False)
    environment: str = Field(default="development")
    
    # Security
    secret_key: str
    encryption_key: str
    cors_origins: List[str] = Field(default=["*"])
    
    # Database
    db_user: str
    db_password: str
    db_host: str
    db_port: int = Field(default=5432)
    db_name: str
    redis_url: str
    
    # OpenAI
    openai_api_key: str
    openai_model: str = Field(default="gpt-4o")
    anthropic_api_key: str
    anthropic_model: str = Field(default="claude-3-5-sonnet-20240620")
    gemini_api_key: str
    gemini_model: str = Field(default="gemini-2.5-pro-preview-03-25")
    # LinkedIn credentials
    linkedin_email: str
    linkedin_password: str
    
    # Logging
    log_level: str = Field(default="INFO")
    
    # Rate Limiting
    max_profiles_per_day: int = Field(default=100)
    max_messages_per_day: int = Field(default=50)
    rate_limit_delay_seconds: float = Field(default=2.5)
    
    # Browser Use Configuration
    browser_headless: bool = Field(default=False)
    browser_proxy_url: Optional[str] = Field(default=None)
    user_agent: str = Field(default="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
    
    @property
    def database_url(self) -> str:
        """
        Construct PostgreSQL connection URL from components.
        This properly handles special characters in the password.
        """
        # URL encode the password to handle special characters
        encoded_password = quote_plus(self.db_password)
        return f"postgresql://{self.db_user}:{encoded_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string to list if needed."""
        if isinstance(v, str) and v != "*":
            return [origin.strip() for origin in v.split(",")]
        return v
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings as a singleton.
    Uses LRU cache for performance.
    """
    return Settings()


settings = get_settings() 