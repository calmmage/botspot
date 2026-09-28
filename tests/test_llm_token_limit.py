import pytest

from botspot.components.new.llm_provider import _token_limit_for


@pytest.mark.parametrize(
    ("model", "key"),
    [
        ("openai/gpt-6-luna", "max_completion_tokens"),
        ("openai/gpt-4.1-nano", "max_completion_tokens"),
        ("anthropic/claude-sonnet-5", "max_tokens"),
        ("gemini/gemini-3.8-flash", "max_tokens"),
        ("xai/grok-4.6", "max_tokens"),
        ("openrouter/openai/gpt-5.6-luna", "max_tokens"),
    ],
)
def test_token_limit_kwarg_per_provider(model, key):
    params = _token_limit_for(model, {"max_tokens": 10, "temperature": 0.2})
    assert params[key] == 10
    assert params["temperature"] == 0.2
    assert len(params) == 2


def test_openai_fallback_to_anthropic_restores_max_tokens():
    openai_params = _token_limit_for("openai/gpt-6-luna", {"max_tokens": 10})
    assert _token_limit_for("anthropic/claude-sonnet-5", openai_params) == {"max_tokens": 10}
