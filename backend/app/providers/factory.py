from .anthropic_provider import AnthropicProvider
from .chat_completions_provider import ChatCompletionsProvider
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
    if settings.llm_provider == "deepseek":
        return ChatCompletionsProvider(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
            provider_name="DeepSeek",
            max_tokens=settings.llm_max_tokens,
            supports_image_input=settings.deepseek_supports_images,
        )
    if settings.llm_provider == "openai_compatible":
        return ChatCompletionsProvider(
            api_key=settings.openai_compatible_api_key,
            base_url=settings.openai_compatible_base_url,
            model=settings.openai_compatible_model,
            provider_name="OpenAI-compatible",
            max_tokens=settings.llm_max_tokens,
            supports_image_input=settings.openai_compatible_supports_images,
        )
    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
