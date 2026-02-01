"""
OpenClaw Claude Provider

Claude API integration using the Anthropic SDK.
"""

import logging
import os
import uuid
from typing import Any

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import BaseLLMProvider, ProviderResponse

logger = logging.getLogger(__name__)


class ClaudeAPIError(Exception):
    """Error from Claude API."""

    pass


class ClaudeProvider(BaseLLMProvider):
    """Provider for Claude API via Anthropic SDK."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        max_retries: int = 3,
        timeout: int = 60,
        api_key: str | None = None,
    ):
        """
        Initialize the Claude provider.

        Args:
            model: Claude model identifier
            max_retries: Maximum retry attempts for rate limits
            timeout: Request timeout in seconds
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self._model = model
        self._max_retries = max_retries
        self._timeout = timeout
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

        if not self._api_key:
            logger.warning("ANTHROPIC_API_KEY not set - Claude provider will not be available")
            self._client = None
        else:
            self._client = anthropic.AsyncAnthropic(
                api_key=self._api_key,
                timeout=timeout,
            )

    @property
    def name(self) -> str:
        return "claude"

    def _convert_messages(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str | None, list[dict[str, str]]]:
        """
        Convert OpenAI-format messages to Anthropic format.

        Anthropic API requires:
        - System message as a separate parameter
        - Messages must alternate between user and assistant roles

        Returns:
            Tuple of (system_message, converted_messages)
        """
        system_message = None
        converted = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                # Accumulate system messages
                if system_message:
                    system_message += "\n\n" + content
                else:
                    system_message = content
            elif role == "assistant":
                converted.append({"role": "assistant", "content": content})
            else:
                # Treat everything else as user
                converted.append({"role": "user", "content": content})

        # Ensure messages alternate properly (Anthropic requirement)
        # If first message is assistant, prepend a placeholder user message
        if converted and converted[0]["role"] == "assistant":
            converted.insert(0, {"role": "user", "content": "Continue."})

        # Merge consecutive same-role messages
        merged = []
        for msg in converted:
            if merged and merged[-1]["role"] == msg["role"]:
                merged[-1]["content"] += "\n\n" + msg["content"]
            else:
                merged.append(msg)

        return system_message, merged

    @retry(
        retry=retry_if_exception_type(anthropic.RateLimitError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _call_api(
        self,
        messages: list[dict[str, str]],
        system: str | None,
        max_tokens: int,
        temperature: float,
        top_p: float,
    ) -> anthropic.types.Message:
        """Call the Anthropic API with retry logic for rate limits."""
        kwargs = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
        }

        if system:
            kwargs["system"] = system

        return await self._client.messages.create(**kwargs)

    async def generate(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> ProviderResponse:
        """
        Generate a response using Claude API.

        Converts OpenAI message format to Anthropic format and handles
        retry logic with exponential backoff for rate limits.
        """
        if not self._client:
            raise ClaudeAPIError("Claude provider not available - API key not configured")

        # Convert message format
        system_message, converted_messages = self._convert_messages(messages)

        if not converted_messages:
            converted_messages = [{"role": "user", "content": "Hello"}]

        try:
            response = await self._call_api(
                messages=converted_messages,
                system=system_message,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            )

            # Extract content from response
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            return ProviderResponse(
                id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
                model=self._model,
                content=content,
                provider=self.name,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                },
                cached=False,
            )

        except anthropic.RateLimitError as e:
            logger.error(f"Claude rate limit exceeded after retries: {e}")
            raise ClaudeAPIError(f"Rate limit exceeded: {e}")

        except anthropic.APIStatusError as e:
            logger.error(f"Claude API error: {e.status_code} - {e.message}")
            raise ClaudeAPIError(f"API error ({e.status_code}): {e.message}")

        except anthropic.APIConnectionError as e:
            logger.error(f"Claude connection error: {e}")
            raise ClaudeAPIError(f"Connection error: {e}")

        except Exception as e:
            logger.error(f"Unexpected Claude error: {e}")
            raise ClaudeAPIError(f"Unexpected error: {e}")

    async def health_check(self) -> bool:
        """Check if the Claude provider is available."""
        return self._client is not None
