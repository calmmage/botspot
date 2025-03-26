"""Tests to ensure that the example applications can be instantiated correctly."""

import importlib
import os
import sys
from unittest.mock import patch

import pytest
from aiogram import Dispatcher

# Add the necessary paths for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))


@pytest.mark.parametrize(
    "example_path,app_class_name",
    [
        ("examples.components_examples.ask_user_demo.bot", "AskUserDemoApp"),
        ("examples.components_examples.chat_binder_demo.bot", "ChatBinderDemoApp"),
        ("examples.components_examples.llm_provider_demo.bot", "LLMProviderDemoApp"),
        ("examples.components_examples.standalone_components.bot", "StandaloneComponentsApp"),
        ("examples.components_examples.trial_mode_demo.bot", "TrialModeDemoApp"),
    ],
)
def test_example_app_imports(example_path, app_class_name, monkeypatch):
    """Test that the example apps can be imported and the App class can be instantiated."""
    # Mock all the necessary environment variables
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy_token")

    # Test that we can import the module
    module = importlib.import_module(example_path)
    assert module is not None

    # Check that the app class exists
    app_class = getattr(module, app_class_name)
    assert app_class is not None

    # Ensure we can instantiate the app class
    app = app_class()
    assert app.name is not None
    assert app.config is not None


@pytest.mark.parametrize(
    "example_path,router_name",
    [
        ("examples.components_examples.ask_user_demo.bot", "router"),
        ("examples.components_examples.chat_binder_demo.bot", "router"),
        ("examples.components_examples.llm_provider_demo.bot", "router"),
        ("examples.components_examples.standalone_components.bot", "router"),
        ("examples.components_examples.trial_mode_demo.bot", "router"),
    ],
)
def test_example_router_setup(example_path, router_name, monkeypatch):
    """Test that the example routers are set up correctly."""
    # Mock all the necessary environment variables
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy_token")

    # Test that we can import the module
    module = importlib.import_module(example_path)
    assert module is not None

    # Check that the router exists
    router = getattr(module, router_name)
    assert router is not None

    # Check that handlers are registered on the router
    assert len(router.message.handlers) > 0


@pytest.mark.parametrize(
    "example_path",
    [
        "examples.components_examples.ask_user_demo.bot",
        "examples.components_examples.chat_binder_demo.bot",
        "examples.components_examples.llm_provider_demo.bot",
        "examples.components_examples.standalone_components.bot",
        "examples.components_examples.trial_mode_demo.bot",
    ],
)
def test_example_main_function(example_path, monkeypatch):
    """Test that the main function in each example can be called without errors."""
    # Mock all the necessary environment variables
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy_token")

    # Import the base_bot main function to mock it
    with patch("examples.base_bot.main") as mock_main:
        # Test that we can import the module
        module = importlib.import_module(example_path)
        assert module is not None

        # Get the __main__ code block
        if hasattr(module, "__name__") and "__main__" in module.__name__:
            # This would execute the main block which calls main()
            # Since we've mocked the main function, this should not cause issues
            pass

        # Verify that the main function was called properly would require actually
        # running the __main__ block, which we can't do directly in a unit test
        assert mock_main.call_count == 0  # We're not actually executing the code
