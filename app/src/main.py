"""
OpenClaw (ClawdBot) - AI-powered bot running on Llama LLM

Main application entry point. Supports Llama (default) or Claude API via toggle.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .llm import LlamaModel
from .config import settings
from .providers import ClaudeProvider
from .cost import CostTracker

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global instances
llm_model: LlamaModel | None = None
claude_provider: ClaudeProvider | None = None
cost_tracker: CostTracker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - handles startup and shutdown."""
    global llm_model, claude_provider, cost_tracker

    logger.info(f"Starting OpenClaw v{settings.version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Provider: {'Claude API' if settings.use_claude else 'Llama (self-hosted)'}")

    if settings.use_claude:
        # Initialize Claude provider
        claude_provider = ClaudeProvider(
            model=settings.claude_model,
            timeout=settings.claude_timeout,
        )

        if not await claude_provider.health_check():
            logger.error("Claude API key not configured")
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        # Initialize cost tracker
        cost_tracker = CostTracker(
            monthly_budget_usd=settings.monthly_budget_usd,
            cloudwatch_namespace=settings.cloudwatch_metrics_namespace,
            aws_region=settings.aws_region,
            enabled=settings.cost_tracking_enabled,
        )

        logger.info(f"Claude model: {settings.claude_model}")
        logger.info(f"Monthly budget: ${settings.monthly_budget_usd}")
    else:
        # Initialize Llama model
        logger.info(f"Loading model: {settings.llama_model}")
        try:
            llm_model = LlamaModel(
                model_name=settings.llama_model,
                quantization=settings.model_quantization,
                cache_dir=settings.model_cache_dir,
            )
            await llm_model.load()
            logger.info("Llama model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    yield

    # Cleanup on shutdown
    logger.info("Shutting down OpenClaw")
    if llm_model:
        await llm_model.unload()


# Create FastAPI application
app = FastAPI(
    title="OpenClaw",
    description="AI-powered bot running on Llama LLM or Claude API",
    version=settings.version,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request/Response Models
# ============================================================================

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9


class ChatResponse(BaseModel):
    id: str
    model: str
    content: str
    usage: dict
    provider: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    model: str
    provider: str
    model_loaded: bool


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for load balancer and monitoring."""
    if settings.use_claude:
        model_loaded = claude_provider is not None
        model_name = settings.claude_model
        provider = "claude"
    else:
        model_loaded = llm_model is not None and llm_model.is_loaded
        model_name = settings.llama_model
        provider = "llama"

    return HealthResponse(
        status="healthy" if model_loaded else "degraded",
        version=settings.version,
        model=model_name,
        provider=provider,
        model_loaded=model_loaded,
    )


@app.get("/")
async def root():
    """Root endpoint with basic info."""
    return {
        "name": "OpenClaw",
        "version": settings.version,
        "description": "AI-powered bot running on Llama LLM or Claude API",
        "docs": "/docs",
        "provider": "claude" if settings.use_claude else "llama",
    }


@app.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(request: ChatRequest):
    """
    Chat completions endpoint (OpenAI-compatible format).

    Uses either Llama (self-hosted) or Claude API based on USE_CLAUDE config.
    """
    if settings.use_claude:
        # Use Claude API
        if not claude_provider:
            raise HTTPException(status_code=503, detail="Claude provider not initialized")

        try:
            # Convert messages to dict format
            messages = [{"role": m.role, "content": m.content} for m in request.messages]

            response = await claude_provider.generate(
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
            )

            # Track costs
            if cost_tracker:
                cost_tracker.track_usage(
                    input_tokens=response.usage.get("prompt_tokens", 0),
                    output_tokens=response.usage.get("completion_tokens", 0),
                    provider="claude",
                )

            return ChatResponse(
                id=response.id,
                model=response.model,
                content=response.content,
                usage=response.usage,
                provider="claude",
            )

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise HTTPException(status_code=502, detail=str(e))

    else:
        # Use Llama
        if not llm_model or not llm_model.is_loaded:
            raise HTTPException(status_code=503, detail="Model not loaded")

        try:
            response = await llm_model.generate(
                messages=request.messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
            )

            return ChatResponse(
                id=response["id"],
                model=response["model"],
                content=response["content"],
                usage=response["usage"],
                provider="llama",
            )

        except Exception as e:
            logger.error(f"Generation error: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
async def list_models():
    """List available models."""
    if settings.use_claude:
        return {
            "data": [
                {
                    "id": settings.claude_model,
                    "object": "model",
                    "owned_by": "anthropic",
                    "provider": "claude",
                }
            ]
        }
    else:
        return {
            "data": [
                {
                    "id": settings.llama_model,
                    "object": "model",
                    "owned_by": "openclaw",
                    "provider": "llama",
                }
            ]
        }


@app.get("/v1/cost/stats")
async def cost_stats():
    """Get cost tracking statistics (only when using Claude)."""
    if not settings.use_claude:
        return {"message": "Cost tracking only available when using Claude API"}

    if not cost_tracker:
        raise HTTPException(status_code=503, detail="Cost tracker not initialized")

    return cost_tracker.get_stats()


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.environment == "development",
        workers=1,  # Single worker for GPU model
    )
