from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import BotCommand

from botspot.components.qol.bot_commands_menu import (
    BotCommandsMenuSettings,
    CommandInfo,
    GroupDisplayMode,
    Visibility,
    add_admin_command,
    add_command,
    add_hidden_command,
    commands,
    get_commands_by_visibility,
    set_aiogram_bot_commands,
    setup_dispatcher,
)


@pytest.fixture(autouse=True)
def clear_commands():
    """Clear the commands dictionary before each test"""
    commands.clear()
    yield
    commands.clear()


class TestBotCommandsMenuSettings:
    def test_default_settings(self):
        """Test default settings"""
        settings = BotCommandsMenuSettings()

        assert settings.enabled is True
        assert settings.admin_id == 0
        assert settings.botspot_help is True
        assert settings.group_display_mode == GroupDisplayMode.NESTED.value
        assert settings.default_group == "General"
        assert settings.display_mode == GroupDisplayMode.NESTED
        assert settings.sort_commands is True  # Sorting enabled by default

    def test_settings_from_env(self):
        """Test settings from environment variables"""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("BOTSPOT_BOT_COMMANDS_MENU_ENABLED", "False")
            mp.setenv("BOTSPOT_BOT_COMMANDS_MENU_ADMIN_ID", "123456789")
            mp.setenv("BOTSPOT_BOT_COMMANDS_MENU_BOTSPOT_HELP", "False")
            mp.setenv("BOTSPOT_BOT_COMMANDS_MENU_GROUP_DISPLAY_MODE", "flat")
            mp.setenv("BOTSPOT_BOT_COMMANDS_MENU_DEFAULT_GROUP", "CustomDefault")
            mp.setenv("BOTSPOT_BOT_COMMANDS_MENU_SORT_COMMANDS", "False")

            settings = BotCommandsMenuSettings()

            assert settings.enabled is False
            assert settings.admin_id == 123456789
            assert settings.botspot_help is False
            assert settings.group_display_mode == "flat"
            assert settings.default_group == "CustomDefault"
            assert settings.display_mode == GroupDisplayMode.FLAT
            assert settings.sort_commands is False


class TestVisibility:
    def test_enum_values(self):
        """Test Visibility enum values"""
        assert Visibility.PUBLIC.value == "public"
        assert Visibility.HIDDEN.value == "hidden"
        assert Visibility.ADMIN_ONLY.value == "admin_only"

    def test_enum_from_string(self):
        """Test creating Visibility enum from string"""
        assert Visibility("public") == Visibility.PUBLIC
        assert Visibility("hidden") == Visibility.HIDDEN
        assert Visibility("admin_only") == Visibility.ADMIN_ONLY


class TestGroupDisplayMode:
    def test_enum_values(self):
        """Test GroupDisplayMode enum values"""
        assert GroupDisplayMode.NESTED.value == "nested"
        assert GroupDisplayMode.FLAT.value == "flat"

    def test_enum_from_string(self):
        """Test creating GroupDisplayMode enum from string"""
        assert GroupDisplayMode("nested") == GroupDisplayMode.NESTED
        assert GroupDisplayMode("flat") == GroupDisplayMode.FLAT


class TestCommandInfo:
    def test_command_info_creation(self):
        """Test creating CommandInfo objects"""
        # With all parameters
        info = CommandInfo("Test description", Visibility.PUBLIC, "TestGroup")
        assert info.description == "Test description"
        assert info.visibility == Visibility.PUBLIC
        assert info.group == "TestGroup"

        # With default visibility
        info = CommandInfo("Test description")
        assert info.description == "Test description"
        assert info.visibility == Visibility.PUBLIC
        assert info.group is None  # Default is now None

        # With custom group
        info = CommandInfo("Test description", group="CustomGroup")
        assert info.description == "Test description"
        assert info.visibility == Visibility.PUBLIC
        assert info.group == "CustomGroup"


class TestGetCommandsByVisibility:
    def test_empty_commands(self):
        """Test get_commands_by_visibility with no commands"""
        assert get_commands_by_visibility() == "No commands available"
        assert get_commands_by_visibility(include_admin=True) == "No commands available"

    def test_public_commands(self):
        """Test get_commands_by_visibility with public commands"""
        commands["test1"] = CommandInfo("Test command 1", Visibility.PUBLIC)
        commands["test2"] = CommandInfo("Test command 2", Visibility.PUBLIC)

        result = get_commands_by_visibility()

        assert "📝 Public commands:" in result
        assert "/test1 - Test command 1" in result
        assert "/test2 - Test command 2" in result

    def test_hidden_commands(self):
        """Test get_commands_by_visibility with hidden commands"""
        commands["test1"] = CommandInfo("Test command 1", Visibility.HIDDEN)
        commands["test2"] = CommandInfo("Test command 2", Visibility.HIDDEN)

        result = get_commands_by_visibility()

        assert "🕵️ Hidden commands:" in result
        assert "/test1 - Test command 1" in result
        assert "/test2 - Test command 2" in result

    def test_admin_commands_included(self):
        """Test get_commands_by_visibility with admin commands included"""
        commands["test1"] = CommandInfo("Test command 1", Visibility.ADMIN_ONLY)
        commands["test2"] = CommandInfo("Test command 2", Visibility.ADMIN_ONLY)

        result = get_commands_by_visibility(include_admin=True)

        assert "👑 Admin commands:" in result
        assert "/test1 - Test command 1" in result
        assert "/test2 - Test command 2" in result

    def test_admin_commands_excluded(self):
        """Test get_commands_by_visibility with admin commands excluded"""
        commands["test1"] = CommandInfo("Test command 1", Visibility.ADMIN_ONLY)
        commands["test2"] = CommandInfo("Test command 2", Visibility.ADMIN_ONLY)

        result = get_commands_by_visibility(include_admin=False)

        assert "No commands available" in result
        assert "👑 Admin commands:" not in result

    def test_mixed_commands(self):
        """Test get_commands_by_visibility with mixed command types"""
        commands["public1"] = CommandInfo("Public command 1", Visibility.PUBLIC)
        commands["public2"] = CommandInfo("Public command 2", Visibility.PUBLIC)
        commands["hidden1"] = CommandInfo("Hidden command 1", Visibility.HIDDEN)
        commands["admin1"] = CommandInfo("Admin command 1", Visibility.ADMIN_ONLY)

        # Without admin commands
        result = get_commands_by_visibility(include_admin=False)

        assert "📝 Public commands:" in result
        assert "/public1 - Public command 1" in result
        assert "/public2 - Public command 2" in result
        assert "🕵️ Hidden commands:" in result
        assert "/hidden1 - Hidden command 1" in result
        assert "👑 Admin commands:" not in result
        assert "/admin1 - Admin command 1" not in result

        # With admin commands
        result = get_commands_by_visibility(include_admin=True)

        assert "📝 Public commands:" in result
        assert "/public1 - Public command 1" in result
        assert "/public2 - Public command 2" in result
        assert "🕵️ Hidden commands:" in result
        assert "/hidden1 - Hidden command 1" in result
        assert "👑 Admin commands:" in result
        assert "/admin1 - Admin command 1" in result

    def test_commands_with_groups(self):
        """Test get_commands_by_visibility with commands in different groups"""
        commands["cmd1"] = CommandInfo("Command 1", Visibility.PUBLIC, "Group1")
        commands["cmd2"] = CommandInfo("Command 2", Visibility.PUBLIC, "Group1")
        commands["cmd3"] = CommandInfo("Command 3", Visibility.PUBLIC, "Group2")
        commands["cmd4"] = CommandInfo("Command 4", Visibility.HIDDEN, "Group1")
        commands["cmd5"] = CommandInfo("Command 5", Visibility.ADMIN_ONLY, "Group3")

        # Get all commands with default nested mode
        settings = BotCommandsMenuSettings(group_display_mode=GroupDisplayMode.NESTED.value)
        result = get_commands_by_visibility(include_admin=True, settings=settings)

        # Check public commands by group
        assert "📝 Public commands:" in result
        assert "Group1:" in result
        assert "Group2:" in result
        assert "/cmd1 - Command 1" in result
        assert "/cmd2 - Command 2" in result
        assert "/cmd3 - Command 3" in result

        # Check hidden commands by group
        assert "🕵️ Hidden commands:" in result
        assert "/cmd4 - Command 4" in result

        # Check admin commands by group
        assert "👑 Admin commands:" in result
        assert "Group3:" in result
        assert "/cmd5 - Command 5" in result

    def test_commands_with_flat_display_mode(self):
        """Test get_commands_by_visibility with flat display mode"""
        # Clear previous commands
        commands.clear()

        # Add commands with different groups
        commands["cmd1"] = CommandInfo("Command 1", Visibility.PUBLIC, "CustomGroup")
        commands["cmd2"] = CommandInfo("Command 2", Visibility.PUBLIC, "CustomGroup")
        commands["cmd3"] = CommandInfo(
            "Command 3", Visibility.PUBLIC, None
        )  # Default group (visibility)
        commands["cmd4"] = CommandInfo("Command 4", Visibility.HIDDEN, "CustomGroup")
        commands["cmd5"] = CommandInfo(
            "Command 5", Visibility.ADMIN_ONLY, None
        )  # Default group (visibility)

        # Get commands with flat display mode
        settings = BotCommandsMenuSettings(group_display_mode=GroupDisplayMode.FLAT.value)
        result = get_commands_by_visibility(include_admin=True, settings=settings)

        # Check groups appear at the same level
        assert "Customgroup:" in result  # This is case sensitive
        assert "📝 Public Commands:" in result
        assert "🕵️ Hidden commands:" not in result  # Hidden command is in CustomGroup
        assert "👑 Admin commands:" in result

        # Check commands in the right groups
        assert "/cmd1 - Command 1" in result
        assert "/cmd2 - Command 2" in result
        assert "/cmd3 - Command 3" in result  # In visibility group
        assert "/cmd4 - Command 4" in result  # In CustomGroup
        assert "/cmd5 - Command 5" in result  # In Admin group


class TestSetAiogramBotCommands:
    @pytest.mark.asyncio
    async def test_set_aiogram_bot_commands(self):
        """Test set_aiogram_bot_commands sets only public commands"""
        with patch("botspot.components.qol.bot_commands_menu.logger"):
            # Add commands of different types
            commands["public1"] = CommandInfo("Public command 1", Visibility.PUBLIC)
            commands["public2"] = CommandInfo("Public command 2", Visibility.PUBLIC)
            commands["hidden1"] = CommandInfo("Hidden command 1", Visibility.HIDDEN)
            commands["admin1"] = CommandInfo("Admin command 1", Visibility.ADMIN_ONLY)

            # Mock bot
            mock_bot = AsyncMock()

            # Call the function with default settings (sorting enabled)
            await set_aiogram_bot_commands(mock_bot)

            # Verify set_my_commands was called with only public commands
            mock_bot.set_my_commands.assert_called_once()
            command_list = mock_bot.set_my_commands.call_args[0][0]

            # Should have 2 commands (public1 and public2)
            assert len(command_list) == 2

            # Verify commands are correct
            assert isinstance(command_list[0], BotCommand)
            assert isinstance(command_list[1], BotCommand)

            # With sorting enabled, commands should be ordered alphabetically
            assert command_list[0].command == "public1"
            assert command_list[0].description == "Public command 1"
            assert command_list[1].command == "public2"
            assert command_list[1].description == "Public command 2"

    @pytest.mark.asyncio
    async def test_set_aiogram_bot_commands_sorting_disabled(self):
        """Test set_aiogram_bot_commands with sorting disabled"""
        with patch("botspot.components.qol.bot_commands_menu.logger"):
            # Add commands in reverse alphabetical order
            commands.clear()
            commands["z_command"] = CommandInfo("Z command", Visibility.PUBLIC)
            commands["a_command"] = CommandInfo("A command", Visibility.PUBLIC)
            commands["m_command"] = CommandInfo("M command", Visibility.PUBLIC)

            # Mock bot
            mock_bot = AsyncMock()

            # Create settings with sorting disabled
            settings = BotCommandsMenuSettings(sort_commands=False)

            # Call the function
            await set_aiogram_bot_commands(mock_bot, settings)

            # Verify set_my_commands was called
            mock_bot.set_my_commands.assert_called_once()
            command_list = mock_bot.set_my_commands.call_args[0][0]

            # Should have 3 commands
            assert len(command_list) == 3

            # With sorting disabled, commands should be in the order they were added
            assert command_list[0].command == "z_command"
            assert command_list[1].command == "a_command"
            assert command_list[2].command == "m_command"

    @pytest.mark.asyncio
    async def test_set_aiogram_bot_commands_sorting_enabled(self):
        """Test set_aiogram_bot_commands with sorting explicitly enabled"""
        with patch("botspot.components.qol.bot_commands_menu.logger"):
            # Add commands in reverse alphabetical order
            commands.clear()
            commands["z_command"] = CommandInfo("Z command", Visibility.PUBLIC)
            commands["a_command"] = CommandInfo("A command", Visibility.PUBLIC)
            commands["m_command"] = CommandInfo("M command", Visibility.PUBLIC)

            # Mock bot
            mock_bot = AsyncMock()

            # Create settings with sorting explicitly enabled
            settings = BotCommandsMenuSettings(sort_commands=True)

            # Call the function
            await set_aiogram_bot_commands(mock_bot, settings)

            # Verify set_my_commands was called
            mock_bot.set_my_commands.assert_called_once()
            command_list = mock_bot.set_my_commands.call_args[0][0]

            # Should have 3 commands
            assert len(command_list) == 3

            # With sorting enabled, commands should be in alphabetical order
            assert command_list[0].command == "a_command"
            assert command_list[1].command == "m_command"
            assert command_list[2].command == "z_command"


class TestSetupDispatcher:
    def test_setup_dispatcher_registers_startup_handler(self):
        """Test setup_dispatcher registers startup handler"""
        # Mock dispatcher
        mock_dispatcher = MagicMock()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.botspot_help = False

        # Call setup_dispatcher
        setup_dispatcher(mock_dispatcher, mock_settings)

        # Verify startup handler is registered (not checking the exact function)
        assert mock_dispatcher.startup.register.called

    def test_setup_dispatcher_with_botspot_help(self):
        """Test setup_dispatcher registers help command when botspot_help is enabled"""
        with patch("botspot.components.qol.bot_commands_menu.add_command") as mock_add_command:
            # Mock dispatcher
            mock_dispatcher = MagicMock()

            # Mock settings
            mock_settings = MagicMock()
            mock_settings.botspot_help = True

            # Call setup_dispatcher
            setup_dispatcher(mock_dispatcher, mock_settings)

            # Verify startup handler registration
            mock_dispatcher.startup.register.assert_called_once()

            # Verify help command addition
            mock_add_command.assert_called_once()
            assert mock_add_command.call_args[0][0] == "help_botspot"

    def test_help_botspot_command(self):
        """Test help_botspot_command is properly added in setup_dispatcher"""
        # This test will focus only on verifying that help_botspot_command is properly
        # registered in setup_dispatcher, which is the main purpose of this test

        with patch("botspot.components.qol.bot_commands_menu.add_command") as mock_add_command:
            # Create mock dispatcher with properly structured methods
            mock_dispatcher = MagicMock()
            mock_decorator = MagicMock()
            mock_dispatcher.message = MagicMock(return_value=mock_decorator)

            # Mock settings
            mock_settings = MagicMock()
            mock_settings.botspot_help = True

            # Call setup_dispatcher
            setup_dispatcher(mock_dispatcher, mock_settings)

            # Verify add_command was called with the correct parameters
            mock_add_command.assert_called_once_with("help_botspot", "Show available bot commands")


class TestAddCommand:
    def test_add_command_with_name_and_description(self):
        """Test add_command with explicit name and description"""

        # Define a function to decorate
        def test_func():
            pass

        # Apply decorator
        decorated = add_command("test_cmd", "Test command description")(test_func)

        # Verify function is returned unchanged
        assert decorated is test_func

        # Verify command is registered
        assert "test_cmd" in commands
        assert commands["test_cmd"].description == "Test command description"
        assert commands["test_cmd"].visibility == Visibility.PUBLIC

    def test_add_command_with_multiple_names(self):
        """Test add_command with multiple command names"""

        # Define a function to decorate
        def test_func():
            pass

        # Apply decorator with multiple names
        decorated = add_command(["cmd1", "cmd2"], "Test command")(test_func)

        # Verify commands are registered
        assert "cmd1" in commands
        assert "cmd2" in commands
        assert commands["cmd1"].description == "Test command"
        assert commands["cmd2"].description == "Test command"

    def test_add_command_without_name(self):
        """Test add_command using function name as command name"""

        # Define a function to decorate
        def test_command_name():
            """Test docstring"""
            pass

        # Apply decorator
        decorated = add_command()(test_command_name)

        # Verify command is registered using function name
        assert "test_command_name" in commands

    def test_add_command_with_docstring(self):
        """Test add_command using docstring as description"""

        # Define a function to decorate
        def test_func():
            """This is a test docstring"""
            pass

        # Apply decorator without description
        decorated = add_command("test_cmd")(test_func)

        # Verify docstring is used as description
        assert commands["test_cmd"].description == "This is a test docstring"

    def test_add_command_existing_command(self):
        """Test add_command with an existing command name"""
        with patch("botspot.components.qol.bot_commands_menu.logger") as mock_logger:
            # Add first command
            commands["existing_cmd"] = CommandInfo("Existing command")

            # Define a function to decorate
            def test_func():
                pass

            # Apply decorator with existing name
            decorated = add_command("existing_cmd", "New description")(test_func)

            # Verify warning is logged
            mock_logger.warning.assert_called_once()

            # Verify command was not overwritten
            assert commands["existing_cmd"].description == "Existing command"


class TestAddHiddenCommand:
    def test_add_hidden_command(self):
        """Test add_hidden_command decorator"""
        with patch("botspot.components.qol.bot_commands_menu.add_command") as mock_add_command:
            # Define a function to decorate
            def test_func():
                pass

            # Apply decorator
            decorated = add_hidden_command("test_cmd", "Test hidden command")(test_func)

            # Verify add_command was called with visibility=Visibility.HIDDEN
            mock_add_command.assert_called_once()
            args, kwargs = mock_add_command.call_args
            assert args[0] == "test_cmd"
            assert args[1] == "Test hidden command"
            assert kwargs["visibility"] == Visibility.HIDDEN


class TestAddAdminCommand:
    def test_add_admin_command(self):
        """Test add_admin_command decorator"""
        with patch("botspot.components.qol.bot_commands_menu.add_command") as mock_add_command:
            # Define a function to decorate
            def test_func():
                pass

            # Apply decorator
            decorated = add_admin_command("test_cmd", "Test admin command")(test_func)

            # Verify add_command was called with visibility=Visibility.ADMIN_ONLY
            mock_add_command.assert_called_once()
            args, kwargs = mock_add_command.call_args
            assert args[0] == "test_cmd"
            assert args[1] == "Test admin command"
            assert kwargs["visibility"] == Visibility.ADMIN_ONLY
