from unittest.mock import MagicMock, patch

import pytest
from aiogram.types import CallbackQuery, Message, User

from botspot.utils.admin_filter import AdminFilter


@pytest.fixture
def mock_deps():
    with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
        deps = MagicMock()
        settings = MagicMock()
        settings.admin_filter.notify_blocked = True
        deps.botspot_settings = settings
        mock_get_deps.return_value = deps
        yield deps


@pytest.fixture
def admin_user():
    user = MagicMock(spec=User)
    user.id = 12345
    user.username = "admin_user"
    return user


@pytest.fixture
def non_admin_user():
    user = MagicMock(spec=User)
    user.id = 67890
    user.username = "regular_user"
    user.is_bot = False
    return user


@pytest.fixture
def mock_message(non_admin_user):
    message = MagicMock(spec=Message)
    message.from_user = non_admin_user

    # Add service message attributes with None as default values
    message.pinned_message = None
    message.new_chat_members = None
    message.left_chat_member = None
    message.new_chat_title = None
    message.new_chat_photo = None
    message.delete_chat_photo = None
    message.group_chat_created = None
    message.supergroup_chat_created = None
    message.channel_chat_created = None
    message.message_auto_delete_timer_changed = None

    return message


@pytest.fixture
def mock_callback_query(non_admin_user):
    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = non_admin_user
    return callback


class TestAdminFilter:
    @pytest.mark.asyncio
    async def test_no_user(self, mock_message):
        """Test handling message with no from_user"""
        # Setup dependency manager
        with patch(
            "botspot.core.dependency_manager.DependencyManager.is_initialized", return_value=True
        ), patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Set message.from_user to None
            mock_message.from_user = None

            # Create and call the filter
            admin_filter = AdminFilter()
            result = await admin_filter(mock_message)

            # Verify the filter rejected the message
            assert result is False
