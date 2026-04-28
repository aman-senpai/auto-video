import os

from .anthropic_provider import AnthropicProvider
from .base import LLMProvider
from .deepseek_provider import DeepSeekProvider
from .gemini import GeminiProvider
from .openai_provider import OpenAIProvider


def get_llm_provider(
    provider_name: str | None = None, model: str | None = None
) -> LLMProvider:
    provider_name = (
        provider_name or os.getenv("AUTO_VIDEO_LLM_PROVIDER", "gemini").lower()
    )

    if provider_name == "gemini":
        return GeminiProvider(default_model=model or "gemini-3-flash-preview")
    elif provider_name == "openai":
        return OpenAIProvider(default_model=model or "gpt-4o")
    elif provider_name == "anthropic" or provider_name == "claude":
        return AnthropicProvider(default_model=model or "claude-3-5-sonnet-20240620")
    elif provider_name == "deepseek":
        return DeepSeekProvider(default_model=model or "deepseek-v4-pro")
    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
