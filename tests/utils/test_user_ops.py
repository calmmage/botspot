from unittest.mock import MagicMock, patch

import pytest
from aiogram.types import User

from botspot.utils.user_ops import (
    UserRecord,
    compare_users,
    get_user_record,
    is_admin,
    is_friend,
    to_user_record,
)


@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = 12345
    user.username = "test_user"
    return user


@pytest.fixture
def user_record():
    return UserRecord(user_id=12345, username="test_user")


@pytest.fixture
def mock_deps():
    with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
        deps = MagicMock()
        deps.botspot_settings.admins = [
            UserRecord(user_id=1, username="admin1"),
            UserRecord(user_id=2, username="admin2"),
        ]
        deps.botspot_settings.friends = [
            UserRecord(user_id=3, username="friend1"),
            UserRecord(user_id=4, username="friend2"),
        ]
        mock_get_deps.return_value = deps
        yield deps


class TestToUserRecord:
    def test_from_user_record(self, user_record):
        """Test converting UserRecord to UserRecord"""
        result = to_user_record(user_record)
        assert result is user_record

    def test_from_user_object(self, mock_user):
        """Test converting User object to UserRecord"""
        result = to_user_record(mock_user)
        assert result.user_id == mock_user.id
        assert result.username == mock_user.username

    def test_from_user_id(self):
        """Test converting user ID to UserRecord"""
        user_id = 12345
        result = to_user_record(user_id)
        assert result.user_id == user_id
        assert result.username is None

    def test_from_string(self):
        """Test converting string to UserRecord"""
        # This test depends on get_user_record, which we'll test separately
        with patch("botspot.utils.user_ops.get_user_record") as mock_get_record:
            mock_record = UserRecord(username="string_user")
            mock_get_record.return_value = mock_record

            result = to_user_record("string_user")

            mock_get_record.assert_called_once_with("string_user")
            assert result is mock_record

    def test_invalid_type(self):
        """Test that invalid types raise ValueError"""
        with pytest.raises(ValueError, match="Invalid user type"):
            to_user_record([1, 2, 3])  # List is not a valid UserLike type


class TestGetUserRecord:
    def test_phone_number(self):
        """Test creating UserRecord from phone number"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup minimal mock for the cache functionality
            mock_deps = MagicMock()
            mock_cache = MagicMock()
            mock_deps.simple_user_cache = mock_cache
            mock_get_deps.return_value = mock_deps
            
            phone = "+12345678901"
            result = get_user_record(phone)
            assert result.phone == phone
            assert result.user_id is None
            assert result.username is None

    def test_numeric_string(self):
        """Test creating UserRecord from numeric string (treated as user_id)"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup minimal mock for the cache functionality
            mock_deps = MagicMock()
            mock_cache = MagicMock()
            mock_cache.get_user.side_effect = Exception("User not found")
            mock_deps.simple_user_cache = mock_cache
            mock_get_deps.return_value = mock_deps
            
            user_id_str = "12345"
            result = get_user_record(user_id_str)
            assert result.user_id == 12345
            assert result.username is None
            assert result.phone is None

    def test_username_with_at(self):
        """Test creating UserRecord from username with @ prefix"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup minimal mock for the cache functionality
            mock_deps = MagicMock()
            mock_cache = MagicMock()
            mock_cache.get_user_by_username.side_effect = Exception("User not found")
            mock_deps.simple_user_cache = mock_cache
            mock_get_deps.return_value = mock_deps
            
            username = "@test_user"
            result = get_user_record(username)
            assert result.username == "test_user"  # @ should be stripped
            assert result.user_id is None
            assert result.phone is None

    def test_username_without_at(self):
        """Test creating UserRecord from username without @ prefix"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup minimal mock for the cache functionality
            mock_deps = MagicMock()
            mock_cache = MagicMock()
            mock_cache.get_user_by_username.side_effect = Exception("User not found")
            mock_deps.simple_user_cache = mock_cache
            mock_get_deps.return_value = mock_deps
            
            username = "test_user"
            result = get_user_record(username)
            assert result.username == username
            assert result.user_id is None
            assert result.phone is None


class TestCompareUsers:
    def test_match_by_id(self):
        """Test that users with matching IDs are considered the same"""
        user1 = UserRecord(user_id=12345, username="user1")
        user2 = UserRecord(user_id=12345, username="different_username")

        assert compare_users(user1, user2) is True

    def test_match_by_username(self):
        """Test that users with matching usernames are considered the same"""
        user1 = UserRecord(user_id=1, username="same_username")
        user2 = UserRecord(user_id=2, username="same_username")

        assert compare_users(user1, user2) is True

    def test_match_by_username_with_at(self):
        """Test that username matching handles @ prefix correctly"""
        user1 = UserRecord(username="test_user")
        user2 = UserRecord(username="@test_user")

        assert compare_users(user1, user2) is True

    def test_match_by_phone(self):
        """Test that users with matching phone numbers are considered the same"""
        user1 = UserRecord(phone="+12345678901")
        user2 = UserRecord(phone="+12345678901")

        assert compare_users(user1, user2) is True

    def test_no_match(self):
        """Test that users with no matching fields are considered different"""
        user1 = UserRecord(user_id=1, username="user1", phone="+11111111111")
        user2 = UserRecord(user_id=2, username="user2", phone="+22222222222")

        assert compare_users(user1, user2) is False

    def test_different_types(self):
        """Test comparison with different input types"""
        # Integer user_id vs User object
        user_id = 12345
        user_obj = MagicMock(spec=User)
        user_obj.id = 12345
        user_obj.username = None

        assert compare_users(user_id, user_obj) is True


class TestIsAdmin:
    def test_admin_by_id(self, mock_deps):
        """Test that a user with an admin ID is recognized as admin"""
        admin_id = 1  # From mock_deps fixture

        assert is_admin(admin_id) is True

    def test_admin_by_username(self, mock_deps):
        """Test that a user with an admin username is recognized as admin"""
        admin_username = "admin1"  # From mock_deps fixture

        assert is_admin(admin_username) is True

    def test_non_admin(self, mock_deps):
        """Test that a non-admin user is not recognized as admin"""
        non_admin_id = 999

        assert is_admin(non_admin_id) is False


class TestIsFriend:
    def test_friend_by_id(self, mock_deps):
        """Test that a user with a friend ID is recognized as friend"""
        friend_id = 3  # From mock_deps fixture

        assert is_friend(friend_id) is True

    def test_friend_by_username(self, mock_deps):
        """Test that a user with a friend username is recognized as friend"""
        friend_username = "friend1"  # From mock_deps fixture

        assert is_friend(friend_username) is True

    def test_non_friend(self, mock_deps):
        """Test that a non-friend user is not recognized as friend"""
        non_friend_id = 999

        assert is_friend(non_friend_id) is False
