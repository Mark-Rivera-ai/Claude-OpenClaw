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

    # Claude API Configuration (manual toggle)
    use_claude: bool = False  # Set to True to use Claude API instead of Llama
    claude_model: str = "claude-sonnet-4-20250514"
    claude_timeout: int = 60

    # Cost Tracking (only applies when using Claude)
    cost_tracking_enabled: bool = True
    monthly_budget_usd: float = 50.0
    cloudwatch_metrics_namespace: str = "OpenClaw/Costs"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
