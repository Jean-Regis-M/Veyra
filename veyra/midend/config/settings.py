"""Configuration settings for VEYRA Midend Infrastructure."""

import os
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    veyra_backend_url: str = Field(
        default="http://127.0.0.1:8000",
        validation_alias="VEYRA_BACKEND_URL",
        description="URL for VEYRA backend HTTP API",
    )
    midend_backend_connector: str = Field(
        default="http",
        validation_alias="MIDEND_BACKEND_CONNECTOR",
        description="Connector type: 'http' or 'mcp'",
    )
    midend_ai_base_url: str = Field(
        default="https://api.llm7.io/v1",
        validation_alias="MIDEND_AI_BASE_URL",
        description="OpenAI-compatible AI API base URL",
    )
    midend_ai_api_key: str = Field(
        default="",
        validation_alias="MIDEND_AI_API_KEY",
        description="OpenAI-compatible API key",
    )
    midend_ai_model: str = Field(
        default="default",
        validation_alias="MIDEND_AI_MODEL",
        description="Default AI model name",
    )
    midend_backend_timeout: float = Field(
        default=30.0,
        validation_alias="MIDEND_BACKEND_TIMEOUT",
        description="Timeout in seconds for backend HTTP calls",
    )
    midend_mcp_timeout: float = Field(
        default=30.0,
        validation_alias="MIDEND_MCP_TIMEOUT",
        description="Timeout in seconds for MCP backend calls",
    )
    midend_ai_timeout: float = Field(
        default=60.0,
        validation_alias="MIDEND_AI_TIMEOUT",
        description="Timeout in seconds for AI provider calls",
    )
    midend_log_level: str = Field(
        default="INFO",
        validation_alias="MIDEND_LOG_LEVEL",
        description="Logging level for midend telemetry",
    )

    class Config:
        env_file = ".env"
        extra = "ignore"


get_settings = Settings
