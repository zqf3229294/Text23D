import pytest

from app.config import Settings
from app.providers.chat_completions_provider import ChatCompletionsProvider
from app.providers.factory import create_provider


def test_deepseek_provider_uses_openai_compatible_chat_provider(tmp_path):
    settings = Settings(
        database_path=tmp_path / "db.sqlite3",
        storage_dir=tmp_path / "artifacts",
        llm_provider="deepseek",
        deepseek_api_key="test-key",
        deepseek_model="deepseek-v4-pro",
        deepseek_supports_images=False,
    )

    provider = create_provider(settings)

    assert isinstance(provider, ChatCompletionsProvider)
    assert provider.model == "deepseek-v4-pro"
    assert provider.supports_image_input is False


def test_openai_compatible_provider_can_opt_into_image_blocks(tmp_path):
    settings = Settings(
        database_path=tmp_path / "db.sqlite3",
        storage_dir=tmp_path / "artifacts",
        llm_provider="openai_compatible",
        openai_compatible_api_key="test-key",
        openai_compatible_base_url="https://example.com",
        openai_compatible_model="vision-model",
        openai_compatible_supports_images=True,
    )

    provider = create_provider(settings)

    assert isinstance(provider, ChatCompletionsProvider)
    assert provider.supports_image_input is True


def test_openai_compatible_provider_requires_model(tmp_path):
    settings = Settings(
        database_path=tmp_path / "db.sqlite3",
        storage_dir=tmp_path / "artifacts",
        llm_provider="openai_compatible",
        openai_compatible_api_key="test-key",
        openai_compatible_base_url="https://example.com",
        openai_compatible_model="",
    )

    with pytest.raises(RuntimeError, match="model"):
        create_provider(settings)
