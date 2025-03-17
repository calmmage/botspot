import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from enum import Enum

from aiogram.types import BotCommand, Message
from botspot.components.qol.bot_commands_menu import (
    BotCommandsMenuSettings,
    Visibility,
    CommandInfo,
    commands,
    get_commands_by_visibility,
    set_aiogram_bot_commands,
    setup_dispatcher,
    add_command,
    add_hidden_command,
    add_admin_command,
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
        
    def test_settings_from_env(self):
        """Test settings from environment variables"""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("BOTSPOT_BOT_COMMANDS_MENU_ENABLED", "False")
            mp.setenv("BOTSPOT_BOT_COMMANDS_MENU_ADMIN_ID", "123456789")
            mp.setenv("BOTSPOT_BOT_COMMANDS_MENU_BOTSPOT_HELP", "False")
            
            settings = BotCommandsMenuSettings()
            
            assert settings.enabled is False
            assert settings.admin_id == 123456789
            assert settings.botspot_help is False


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


class TestCommandInfo:
    def test_command_info_creation(self):
        """Test creating CommandInfo objects"""
        # With all parameters
        info = CommandInfo("Test description", Visibility.PUBLIC)
        assert info.description == "Test description"
        assert info.visibility == Visibility.PUBLIC
        
        # With default visibility
        info = CommandInfo("Test description")
        assert info.description == "Test description"
        assert info.visibility == Visibility.PUBLIC


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


class TestSetAiogramBotCommands:
    @pytest.mark.asyncio
    async def test_set_aiogram_bot_commands(self):
        """Test set_aiogram_bot_commands sets only public commands"""
        with patch('botspot.components.qol.bot_commands_menu.logger'):
            # Add commands of different types
            commands["public1"] = CommandInfo("Public command 1", Visibility.PUBLIC)
            commands["public2"] = CommandInfo("Public command 2", Visibility.PUBLIC)
            commands["hidden1"] = CommandInfo("Hidden command 1", Visibility.HIDDEN)
            commands["admin1"] = CommandInfo("Admin command 1", Visibility.ADMIN_ONLY)
            
            # Mock bot
            mock_bot = AsyncMock()
            
            # Call the function
            await set_aiogram_bot_commands(mock_bot)
            
            # Verify set_my_commands was called with only public commands
            mock_bot.set_my_commands.assert_called_once()
            command_list = mock_bot.set_my_commands.call_args[0][0]
            
            # Should have 2 commands (public1 and public2)
            assert len(command_list) == 2
            
            # Verify commands are correct
            assert isinstance(command_list[0], BotCommand)
            assert isinstance(command_list[1], BotCommand)
            
            # Sort commands by name for consistent test results
            command_list.sort(key=lambda x: x.command)
            
            assert command_list[0].command == "public1"
            assert command_list[0].description == "Public command 1"
            assert command_list[1].command == "public2"
            assert command_list[1].description == "Public command 2"


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
        
        # Verify startup handler registration
        mock_dispatcher.startup.register.assert_called_once_with(set_aiogram_bot_commands)
        
    def test_setup_dispatcher_with_botspot_help(self):
        """Test setup_dispatcher registers help command when botspot_help is enabled"""
        with patch('botspot.components.qol.bot_commands_menu.add_command') as mock_add_command:
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
        
        with patch('botspot.components.qol.bot_commands_menu.add_command') as mock_add_command:
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
            mock_add_command.assert_called_once_with('help_botspot', 'Show available bot commands')


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
        with patch('botspot.components.qol.bot_commands_menu.logger') as mock_logger:
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
        with patch('botspot.components.qol.bot_commands_menu.add_command') as mock_add_command:
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
        with patch('botspot.components.qol.bot_commands_menu.add_command') as mock_add_command:
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