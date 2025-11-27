"""Configuration management for Sehat Saathi"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Environment
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # Google Cloud & Gemini
    google_cloud_project: str = Field(default="", alias="GOOGLE_CLOUD_PROJECT")
    google_application_credentials: str = Field(default="", alias="GOOGLE_APPLICATION_CREDENTIALS")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    google_maps_api_key: str = Field(default="", alias="GOOGLE_MAP_API")
    gemini_model: str = Field(default="gemini-2.0-flash-exp", alias="GEMINI_MODEL")
    gemini_temperature: float = Field(default=0.7, alias="GEMINI_TEMPERATURE")
    gemini_max_tokens: int = Field(default=2048, alias="GEMINI_MAX_TOKENS")

    # Twilio Configuration
    twilio_account_sid: str = Field(default="", alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(default="", alias="TWILIO_AUTH_TOKEN")
    twilio_whatsapp_number: str = Field(default="", alias="TWILIO_WHATSAPP_NUMBER")
    twilio_phone_number: str = Field(default="", alias="TWILIO_PHONE_NUMBER")
    twilio_assistant_id: str = Field(default="", alias="TWILIO_ASSISTANT_ID")

    # Voice/TTS Configuration (Uplift AI)
    uplift_api_key: str = Field(default="", alias="UPLIFT_API_KEY")
    voice_enabled: bool = Field(default=True, alias="VOICE_ENABLED")
    voice_default_language: str = Field(default="ur", alias="VOICE_DEFAULT_LANGUAGE")
    voice_default_voice_id: str = Field(default="v_8eelc901", alias="VOICE_DEFAULT_VOICE_ID")
    voice_output_format: str = Field(default="MP3_22050_64", alias="VOICE_OUTPUT_FORMAT")

    # Database
    database_url: str = Field(default="sqlite:///./sehat_saathi.db", alias="DATABASE_URL")

    # MCP Server
    mcp_server_host: str = Field(default="0.0.0.0", alias="MCP_SERVER_HOST")
    mcp_server_port: int = Field(default=8000, alias="MCP_SERVER_PORT")
    mcp_secret_key: str = Field(default="your-secret-key-change-in-production", alias="MCP_SECRET_KEY")

    # Agent Configuration
    agent_reasoning_temperature: float = Field(default=0.7, alias="AGENT_REASONING_TEMPERATURE")
    agent_max_negotiation_rounds: int = Field(default=3, alias="AGENT_MAX_NEGOTIATION_ROUNDS")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default="logs/sehat_saathi.log", alias="LOG_FILE")

    # Data paths
    data_dir: Path = Field(default=Path("data"))
    hospitals_csv: Path = Field(default=Path("data/hospitals.csv"))
    doctors_csv: Path = Field(default=Path("data/doctors.csv"))
    medicines_csv: Path = Field(default=Path("data/medicines.csv"))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings"""
    return settings
