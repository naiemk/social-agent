"""
Configuration management for the social media agent.

This module provides centralized configuration management using environment variables
and sensible defaults. All configuration is validated and typed using Pydantic.
"""

import os
import logging
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Twitter/X API Configuration (Auth v2 with Bearer Token - Primary)
    twitter_bearer_token: str = Field(..., env="TWITTER_BEARER_TOKEN")
    twitter_user_id: str = Field(..., env="TWITTER_USER_ID")
    
    # Tweepy Configuration (for OAuth 1.0a authentication - Optional)
    twitter_api_key: Optional[str] = Field(None, env="TWITTER_API_KEY")
    twitter_api_secret: Optional[str] = Field(None, env="TWITTER_API_SECRET")
    twitter_access_token: Optional[str] = Field(None, env="TWITTER_ACCESS_TOKEN")
    twitter_access_token_secret: Optional[str] = Field(None, env="TWITTER_ACCESS_TOKEN_SECRET")
    
    # Model Configuration
    model_name: str = Field("gemini-2.0-flash-exp", env="MODEL_NAME")
    google_api_key: Optional[str] = Field(None, env="GOOGLE_API_KEY")
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    
    # Search Configuration
    search_terms: List[str] = Field(default=["python", "AI", "agent"], env="SEARCH_TERMS")
    max_tweets_per_run: int = Field(10, env="MAX_TWEETS_PER_RUN")
    
    # Rate Limiting and Safety
    max_likes_per_day: int = Field(20, env="MAX_LIKES_PER_DAY")
    max_replies_per_day: int = Field(10, env="MAX_REPLIES_PER_DAY")
    rate_limit_backoff: int = Field(60, env="RATE_LIMIT_BACKOFF")
    
    # Database Configuration
    database_path: str = Field("/tmp/agent_state.db", env="DATABASE_PATH")
    
    # Scheduling Configuration
    schedule_hours: str = Field("*/3", env="SCHEDULE_HOURS")  # Every 3 hours
    schedule_minutes: Optional[str] = Field(None, env="SCHEDULE_MINUTES")
    disable_scheduler: bool = Field(False, env="DISABLE_SCHEDULER")
    run_forever: bool = Field(False, env="RUN_FOREVER")
    
    # Logging Configuration
    log_level: str = Field("INFO", env="LOG_LEVEL")
    
    # Kernel Configuration
    kernel_confidence_threshold: float = Field(0.7, env="KERNEL_CONFIDENCE_THRESHOLD")
    max_conversation_depth: int = Field(2, env="MAX_CONVERSATION_DEPTH")
    
    @validator('search_terms', pre=True)
    def parse_search_terms(cls, v):
        """Parse comma-separated search terms."""
        if isinstance(v, str):
            return [term.strip() for term in v.split(',') if term.strip()]
        return v
    
    @validator('log_level')
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()
    
    @validator('model_name')
    def validate_model_name(cls, v):
        """Validate model name format."""
        valid_models = [
            'gemini-2.0-flash-exp', 'gemini-2.5-pro', 'gemini-1.5-pro',
            'gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'
        ]
        if v not in valid_models:
            raise ValueError(f"Model must be one of {valid_models}")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_model_api_key() -> str:
    """Get the appropriate API key based on the model being used."""
    if settings.model_name.startswith('gemini'):
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required for Gemini models")
        return settings.google_api_key
    elif settings.model_name.startswith('gpt'):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI models")
        return settings.openai_api_key
    else:
        raise ValueError(f"Unknown model type: {settings.model_name}")


def validate_required_credentials():
    """Validate that all required credentials are present."""
    missing = []
    
    # Check for Twitter authentication (Bearer Token is primary, OAuth 1.0a is optional)
    has_bearer_token = bool(settings.twitter_bearer_token)
    has_oauth_credentials = all([
        settings.twitter_api_key,
        settings.twitter_api_secret,
        settings.twitter_access_token,
        settings.twitter_access_token_secret
    ])
    
    # Bearer token is required for Auth v2
    if not has_bearer_token:
        missing.append("TWITTER_BEARER_TOKEN (required for Auth v2)")
    
    if not settings.twitter_user_id:
        missing.append("TWITTER_USER_ID")
    
    # OAuth credentials are optional - only needed for write operations
    if not has_oauth_credentials:
        logger.warning("OAuth credentials not provided - write operations (like, reply) will be limited")
    
    try:
        get_model_api_key()
    except ValueError as e:
        missing.append(str(e))
    
    if missing:
        raise ValueError(f"Missing required credentials: {', '.join(missing)}")
