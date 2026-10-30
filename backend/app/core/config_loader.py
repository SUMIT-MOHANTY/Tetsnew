"""
DERTOUR Configuration Loader
Pydantic Settings with .env support and DATABASE_URL parsing
"""

import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application
    APP_NAME: str = Field(default="DERTOUR Portfolio Control Tower", alias="APP_NAME")
    APP_VERSION: str = Field(default="1.0.0", alias="APP_VERSION")
    DEBUG: bool = Field(default=False, alias="DEBUG")
    ENVIRONMENT: str = Field(default="development", alias="ENVIRONMENT")
    
    # Database - Supports SQLite (default) and PostgreSQL
    DATABASE_URL: Optional[str] = Field(default=None, alias="DATABASE_URL")
    DATABASE_POOL_SIZE: int = Field(default=5, alias="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(default=10, alias="DATABASE_MAX_OVERFLOW")
    DATABASE_ECHO: bool = Field(default=False, alias="DATABASE_ECHO")
    
    # SQLite specific (used when DATABASE_URL is not set)
    SQLITE_PATH: str = Field(default="./data/app.db", alias="SQLITE_PATH")
    
    # Security
    SECRET_KEY: str = Field(default="dertour-dev-secret-key-change-in-production", alias="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    ALGORITHM: str = Field(default="HS256", alias="ALGORITHM")
    
    # CORS
    CORS_ORIGINS: str = Field(default="http://localhost:3000,http://localhost:5173", alias="CORS_ORIGINS")
    
    # DERTOUR Specific Configuration
    DERTOUR_TERMINOLOGY_PROJECT: str = Field(default="Initiative", alias="DERTOUR_TERMINOLOGY_PROJECT")
    DERTOUR_TERMINOLOGY_WORKSTREAM: str = Field(default="Milestone", alias="DERTOUR_TERMINOLOGY_WORKSTREAM")
    
    # Thresholds
    DELAY_TOLERANCE_DAYS: int = Field(default=7, alias="DELAY_TOLERANCE_DAYS")
    RISK_ESCALATION_THRESHOLD: str = Field(default="HIGH", alias="RISK_ESCALATION_THRESHOLD")
    
    # Workflow Rules
    APPROVAL_MATERIAL_ACTION_ROLES: str = Field(default="EXECUTIVE,PMO", alias="APPROVAL_MATERIAL_ACTION_ROLES")
    APPROVAL_BUDGET_CHANGE_ROLES: str = Field(default="EXECUTIVE", alias="APPROVAL_BUDGET_CHANGE_ROLES")
    APPROVAL_SCOPE_CHANGE_ROLES: str = Field(default="PMO,EXECUTIVE", alias="APPROVAL_SCOPE_CHANGE_ROLES")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"
    
    @field_validator("CORS_ORIGINS")
    @classmethod
    def parse_cors_origins(cls, v: str) -> List[str]:
        """Parse comma-separated CORS origins into list."""
        return [origin.strip() for origin in v.split(",")]
    
    @field_validator("APPROVAL_MATERIAL_ACTION_ROLES", "APPROVAL_BUDGET_CHANGE_ROLES", "APPROVAL_SCOPE_CHANGE_ROLES")
    @classmethod
    def parse_role_lists(cls, v: str) -> List[str]:
        """Parse comma-separated role lists."""
        return [role.strip() for role in v.split(",")]
    
    def get_database_url(self) -> str:
        """
        Get the effective database URL.
        Returns PostgreSQL URL if set, otherwise SQLite path.
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        
        # Ensure data directory exists for SQLite
        sqlite_dir = os.path.dirname(self.SQLITE_PATH)
        if sqlite_dir and not os.path.exists(sqlite_dir):
            os.makedirs(sqlite_dir, exist_ok=True)
        
        return f"sqlite+aiosqlite:///{self.SQLITE_PATH}"
    
    def is_postgres(self) -> bool:
        """Check if using PostgreSQL database."""
        db_url = self.get_database_url()
        return "postgresql" in db_url.lower() or "postgres" in db_url.lower()
    
    def is_sqlite(self) -> bool:
        """Check if using SQLite database."""
        return "sqlite" in self.get_database_url().lower()


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings singleton."""
    return settings
