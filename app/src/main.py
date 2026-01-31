"""
OpenClaw (ClawdBot) - AI-powered bot running on Llama LLM

Main application entry point.
"""

import os
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .llm import LlamaModel
from .config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global model instance
llm_model: LlamaModel | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - handles startup and shutdown."""
    global llm_model

    logger.info(f"Starting OpenClaw v{settings.version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Loading model: {settings.llama_model}")

    # Initialize the LLM model
    try:
        llm_model = LlamaModel(
            model_name=settings.llama_model,
            quantization=settings.model_quantization,
            cache_dir=settings.model_cache_dir,
        )
        await llm_model.load()
        logger.info("Model loaded successfully")
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
    description="AI-powered bot running on Llama LLM",
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


class HealthResponse(BaseModel):
    status: str
    version: str
    model: str
    model_loaded: bool


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for load balancer and monitoring."""
    return HealthResponse(
        status="healthy",
        version=settings.version,
        model=settings.llama_model,
        model_loaded=llm_model is not None and llm_model.is_loaded,
    )


@app.get("/")
async def root():
    """Root endpoint with basic info."""
    return {
        "name": "OpenClaw",
        "version": settings.version,
        "description": "AI-powered bot running on Llama LLM",
        "docs": "/docs",
    }


@app.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(request: ChatRequest):
    """
    Chat completions endpoint (OpenAI-compatible format).

    Send messages to the Llama model and receive a response.
    """
    if not llm_model or not llm_model.is_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        response = await llm_model.generate(
            messages=request.messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
        )
        return response
    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
async def list_models():
    """List available models."""
    return {
        "data": [
            {
                "id": settings.llama_model,
                "object": "model",
                "owned_by": "openclaw",
            }
        ]
    }


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
