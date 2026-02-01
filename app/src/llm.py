"""
OpenClaw LLM Module

Handles loading and inference with Llama models.
"""

import logging
import uuid
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

logger = logging.getLogger(__name__)


class LlamaGenerationError(Exception):
    """Error during Llama text generation."""

    pass


class LlamaResourceError(Exception):
    """Error related to Llama resource availability (GPU OOM, model not loaded)."""

    pass

# Model name mappings to HuggingFace model IDs
MODEL_MAPPINGS = {
    "llama-3.2-1b": "meta-llama/Llama-3.2-1B-Instruct",
    "llama-3.2-3b": "meta-llama/Llama-3.2-3B-Instruct",
    "llama-3.1-8b": "meta-llama/Llama-3.1-8B-Instruct",
    "llama-3.1-70b": "meta-llama/Llama-3.1-70B-Instruct",
    "llama-3.1-405b": "meta-llama/Llama-3.1-405B-Instruct",
}


class LlamaModel:
    """Wrapper for Llama model inference."""

    def __init__(
        self,
        model_name: str,
        quantization: str = "none",
        cache_dir: str = "/app/models",
    ):
        self.model_name = model_name
        self.quantization = quantization
        self.cache_dir = cache_dir

        self.model = None
        self.tokenizer = None
        self.is_loaded = False

        # Resolve model ID
        self.model_id = MODEL_MAPPINGS.get(model_name, model_name)
        logger.info(f"Model ID resolved: {model_name} -> {self.model_id}")

    async def load(self) -> None:
        """Load the model and tokenizer."""
        logger.info(f"Loading model: {self.model_id}")

        # Determine device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")

        if device == "cuda":
            logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
            logger.info(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

        # Configure quantization
        quantization_config = None
        if self.quantization == "int8":
            quantization_config = BitsAndBytesConfig(load_in_8bit=True)
            logger.info("Using INT8 quantization")
        elif self.quantization == "int4":
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
            )
            logger.info("Using INT4 quantization")

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            cache_dir=self.cache_dir,
            trust_remote_code=True,
        )

        # Set pad token if not set
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Load model
        model_kwargs: dict[str, Any] = {
            "cache_dir": self.cache_dir,
            "trust_remote_code": True,
            "device_map": "auto",
        }

        if quantization_config:
            model_kwargs["quantization_config"] = quantization_config
        elif device == "cuda":
            model_kwargs["torch_dtype"] = torch.float16

        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            **model_kwargs,
        )

        self.is_loaded = True
        logger.info("Model loaded successfully")

    async def unload(self) -> None:
        """Unload the model from memory."""
        if self.model:
            del self.model
            self.model = None
        if self.tokenizer:
            del self.tokenizer
            self.tokenizer = None

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        self.is_loaded = False
        logger.info("Model unloaded")

    async def generate(
        self,
        messages: list[dict],
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> dict:
        """Generate a response from the model."""
        if not self.is_loaded:
            raise LlamaResourceError("Model not loaded")

        try:
            # Format messages for Llama chat template
            # Handle both Pydantic models (with .role attribute) and dicts
            formatted_messages = []
            for msg in messages:
                if hasattr(msg, "role"):
                    formatted_messages.append({"role": msg.role, "content": msg.content})
                else:
                    formatted_messages.append({"role": msg["role"], "content": msg["content"]})

            # Apply chat template
            prompt = self.tokenizer.apply_chat_template(
                formatted_messages,
                tokenize=False,
                add_generation_prompt=True,
            )

            # Tokenize
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=4096 - max_tokens,
            )

            # Move to device
            inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    do_sample=temperature > 0,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )

            # Decode response (only the new tokens)
            input_length = inputs["input_ids"].shape[1]
            response_tokens = outputs[0][input_length:]
            response_text = self.tokenizer.decode(response_tokens, skip_special_tokens=True)

            # Calculate usage
            prompt_tokens = input_length
            completion_tokens = len(response_tokens)

            return {
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "model": self.model_name,
                "content": response_text,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
            }

        except torch.cuda.OutOfMemoryError as e:
            logger.error(f"GPU out of memory: {e}")
            # Try to recover by clearing cache
            torch.cuda.empty_cache()
            raise LlamaResourceError(f"GPU out of memory: {e}")

        except RuntimeError as e:
            error_msg = str(e).lower()
            if "cuda" in error_msg or "out of memory" in error_msg:
                logger.error(f"CUDA/Memory error: {e}")
                torch.cuda.empty_cache()
                raise LlamaResourceError(f"GPU resource error: {e}")
            logger.error(f"Runtime error during generation: {e}")
            raise LlamaGenerationError(f"Generation failed: {e}")

        except Exception as e:
            logger.error(f"Unexpected error during generation: {e}")
            raise LlamaGenerationError(f"Generation failed: {e}")
