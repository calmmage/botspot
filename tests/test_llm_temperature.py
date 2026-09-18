"""Temperature handling in llm_provider: omit it for models that reject it, no MagicMock."""

import litellm
import pytest
from litellm.types.utils import ModelResponse

from botspot.components.new import llm_provider
from botspot.components.new.llm_provider import (
    LLMProvider,
    LLMProviderSettings,
    initialize as llm_initialize,
)

OPENAI_REJECTION = (
    "litellm.BadRequestError: OpenAIException - Unsupported value: 'temperature' does not "
    "support 0.3 with this model. Only the default (1) value is supported."
)
ANTHROPIC_REJECTION = (
    "litellm.UnsupportedParamsError: claude-sonnet-5 does not support temperature=0.7. "
    "Only temperature=1 is supported. To drop unsupported params, set litellm.drop_params = True."
)


def make_provider(**overrides) -> LLMProvider:
    settings = LLMProviderSettings(
        enabled=True,
        skip_import_check=True,
        allow_everyone=True,
        drop_unsupported_params=False,
        **overrides,
    )
    return LLMProvider(settings)


def fake_acompletion(calls: list, reject_temperature_with: str | None = None):
    """Real coroutine standing in for litellm.acompletion; records every call."""

    async def _acompletion(**kwargs):
        calls.append(kwargs)
        if reject_temperature_with and "temperature" in kwargs:
            raise Exception(reject_temperature_with)
        return ModelResponse(choices=[{"message": {"content": "ok", "role": "assistant"}}])

    return _acompletion


@pytest.fixture(autouse=True)
def forget_rejected_models():
    llm_provider._TEMPERATURE_REJECTED_MODELS.clear()
    yield
    llm_provider._TEMPERATURE_REJECTED_MODELS.clear()


@pytest.fixture(autouse=True)
def deps():
    """_prepare_request reads botspot settings through the dependency manager."""
    from botspot.core.dependency_manager import DependencyManager

    return DependencyManager()


class TestTemperatureSupportDetection:
    @pytest.mark.asyncio
    async def test_default_temperature_omitted_when_litellm_lacks_it(self, monkeypatch):
        monkeypatch.setattr(
            litellm, "get_supported_openai_params", lambda model, **kw: ["max_tokens", "stream"]
        )
        provider = make_provider()
        params = await provider._prepare_request("hi", user=1, model="openai/no-temp-model")
        assert params["temperature"] is None
        api_params = provider._build_api_params(params, max_retries=0, extra_kwargs={})
        assert "temperature" not in api_params

    @pytest.mark.asyncio
    async def test_default_temperature_sent_when_supported(self, monkeypatch):
        monkeypatch.setattr(
            litellm, "get_supported_openai_params", lambda model, **kw: ["temperature"]
        )
        provider = make_provider(default_temperature=0.4)
        params = await provider._prepare_request("hi", user=1, model="openai/gpt-4o")
        assert params["temperature"] == 0.4
        assert provider._build_api_params(params, 0, {})["temperature"] == 0.4

    @pytest.mark.asyncio
    async def test_explicit_temperature_sent_for_supporting_model(self, monkeypatch):
        monkeypatch.setattr(
            litellm, "get_supported_openai_params", lambda model, **kw: ["temperature"]
        )
        provider = make_provider()
        params = await provider._prepare_request(
            "hi", user=1, model="openai/gpt-4o", temperature=0.2
        )
        assert params["temperature"] == 0.2

    @pytest.mark.asyncio
    async def test_explicit_temperature_on_o_series_maps_to_one(self, monkeypatch):
        monkeypatch.setattr(
            litellm, "get_supported_openai_params", lambda model, **kw: ["temperature"]
        )
        provider = make_provider()
        params = await provider._prepare_request("hi", user=1, model="openai/o3", temperature=0.2)
        assert params["temperature"] == 1

    def test_litellm_errors_count_as_supported(self, monkeypatch):
        def boom(model, **kw):
            raise RuntimeError("no model map")

        monkeypatch.setattr(litellm, "get_supported_openai_params", boom)
        assert LLMProvider._model_supports_temperature("totally/unknown-model") is True


class TestServerSideRejectionFallback:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("error_text", [OPENAI_REJECTION, ANTHROPIC_REJECTION])
    async def test_rejection_retries_once_without_temperature_and_remembers(
        self, monkeypatch, error_text
    ):
        calls: list = []
        monkeypatch.setattr(litellm, "acompletion", fake_acompletion(calls, error_text))
        monkeypatch.setattr(
            litellm, "get_supported_openai_params", lambda model, **kw: ["temperature"]
        )
        provider = make_provider()

        response = await provider.aquery_llm_raw("hi", user=1, model="openai/gpt-5.6-luna")

        assert response.choices[0].message.content == "ok"
        assert len(calls) == 2
        assert calls[0]["temperature"] == 0.7
        assert "temperature" not in calls[1]
        assert calls[1]["max_tokens"] == calls[0]["max_tokens"]
        assert "openai/gpt-5.6-luna" in llm_provider._TEMPERATURE_REJECTED_MODELS

        # Later calls to the same model skip temperature immediately, even explicit ones
        calls.clear()
        await provider.aquery_llm_raw("hi", user=1, model="openai/gpt-5.6-luna", temperature=0.3)
        assert len(calls) == 1
        assert "temperature" not in calls[0]

    @pytest.mark.asyncio
    async def test_unrelated_error_is_not_retried(self, monkeypatch):
        calls: list = []

        async def broken(**kwargs):
            calls.append(kwargs)
            raise ValueError("model not found")

        monkeypatch.setattr(litellm, "acompletion", broken)
        monkeypatch.setattr(
            litellm, "get_supported_openai_params", lambda model, **kw: ["temperature"]
        )
        provider = make_provider()

        with pytest.raises(ValueError, match="model not found"):
            await provider.aquery_llm_raw("hi", user=1, model="openai/gpt-4o")
        assert len(calls) == 1
        assert llm_provider._TEMPERATURE_REJECTED_MODELS == set()

    @pytest.mark.asyncio
    async def test_rejection_without_temperature_in_call_is_not_retried(self, monkeypatch):
        calls: list = []

        async def always_reject(**kwargs):
            calls.append(kwargs)
            raise Exception(OPENAI_REJECTION)

        monkeypatch.setattr(litellm, "acompletion", always_reject)
        with pytest.raises(Exception, match="Unsupported value"):
            await LLMProvider._acompletion("openai/x", [], {"max_tokens": 5})
        assert len(calls) == 1


class TestDropParamsSetting:
    def test_drop_params_set_when_enabled(self, monkeypatch):
        monkeypatch.setattr(litellm, "drop_params", False)
        provider = llm_initialize(
            LLMProviderSettings(enabled=True, skip_import_check=True, drop_unsupported_params=True)
        )
        assert provider is not None
        assert litellm.drop_params is True

    def test_drop_params_untouched_when_disabled(self, monkeypatch):
        monkeypatch.setattr(litellm, "drop_params", False)
        llm_initialize(
            LLMProviderSettings(enabled=True, skip_import_check=True, drop_unsupported_params=False)
        )
        assert litellm.drop_params is False

    def test_default_is_enabled_and_env_overrides(self, monkeypatch):
        assert LLMProviderSettings().drop_unsupported_params is True
        monkeypatch.setenv("BOTSPOT_LLM_PROVIDER_DROP_UNSUPPORTED_PARAMS", "false")
        assert LLMProviderSettings().drop_unsupported_params is False
