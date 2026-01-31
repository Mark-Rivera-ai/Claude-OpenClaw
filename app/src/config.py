"""
OpenClaw Configuration

Application settings loaded from environment variables.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Application
    version: str = "0.1.0"
    environment: str = "development"
    port: int = 8080
    log_level: str = "INFO"

    # CORS
    cors_origins: list[str] = ["*"]

    # LLM Configuration
    llama_model: str = "llama-3.1-8b"
    model_quantization: str = "none"
    model_cache_dir: str = "/app/models"

    # AWS Configuration (optional)
    aws_region: str = "us-east-1"
    model_bucket: str = ""

    # Inference Settings
    max_batch_size: int = 1
    max_sequence_length: int = 4096

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
