"""
OpenClaw Provider Base Classes

Abstract base class and response model for LLM providers.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ProviderResponse(BaseModel):
    """Standardized response from any LLM provider."""

    id: str
    model: str
    content: str
    provider: str  # "llama" or "claude"
    usage: dict[str, int]
    cached: bool = False


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""
        pass

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> ProviderResponse:
        """
        Generate a response from the provider.

        Args:
            messages: List of chat messages with 'role' and 'content' keys
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)
            top_p: Nucleus sampling parameter

        Returns:
            ProviderResponse with the generated content and metadata
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the provider is healthy and ready.

        Returns:
            True if provider is ready, False otherwise
        """
        pass
