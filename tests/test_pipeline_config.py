import pytest

from slideforge.pipeline.config import GenerationConfig, MissingApiKeyError


def test_generation_config_requires_deepseek_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(MissingApiKeyError) as exc:
        GenerationConfig.from_env()

    assert "DEEPSEEK_API_KEY" in str(exc.value)


def test_generation_config_disables_images_without_provider_keys(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("ENABLE_IMAGE_SEARCH", "true")
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)

    config = GenerationConfig.from_env()

    assert config.api_key == "sk-test"
    assert config.enable_images is False
    assert config.image_disable_reason == "missing image provider API key"


def test_generation_config_respects_feature_flags(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("ENABLE_IMAGE_SEARCH", "false")
    monkeypatch.setenv("ENABLE_CHART_GENERATION", "false")
    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "unsplash")

    config = GenerationConfig.from_env()

    assert config.enable_images is False
    assert config.enable_charts is False
    assert config.image_disable_reason == "disabled by ENABLE_IMAGE_SEARCH"
