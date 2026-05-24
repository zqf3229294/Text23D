from .anthropic_provider import AnthropicProvider
from .mock import MockLLMProvider
from .openai_provider import OpenAIProvider
from ..config import Settings


def create_provider(settings: Settings):
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    if settings.llm_provider == "openai":
        return OpenAIProvider(settings)
    if settings.llm_provider == "anthropic":
        return AnthropicProvider(settings)
    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
