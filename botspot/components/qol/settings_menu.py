"""Settings Menu Component for Botspot

This module provides a configurable UI for managing bot settings with two modes:
1. Admin settings - configure botspot components (admin-only)
2. User settings - customizable per-user preferences

It supports both inline keyboard and web app interfaces.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

from aiogram import Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from botspot.components.data.user_data import User, get_user_manager
from botspot.utils.admin_filter import AdminFilter
from botspot.utils.internal import get_logger

logger = get_logger()


# ---------------------------------------------
# region Settings Types and Classes
# ---------------------------------------------


class SettingType(Enum):
    """Types of settings that can be configured"""

    BOOLEAN = "boolean"  # True/False toggle
    OPTION = "option"    # Select from predefined options
    TEXT = "text"        # Free text input
    NUMBER = "number"    # Numeric input
    MODEL = "model"      # Special case for model selection


class SettingCategory(Enum):
    """Categories of settings"""

    GENERAL = "general"
    APPEARANCE = "appearance"
    NOTIFICATIONS = "notifications"
    PRIVACY = "privacy"
    MODELS = "models"
    ADVANCED = "advanced"


class SettingVisibility(Enum):
    """Who can see/modify the setting"""

    ADMIN = "admin"      # Only admins can see/modify
    USER = "user"        # Users can see/modify their own settings
    ALL = "all"          # All users can see/modify


class Setting(BaseModel):
    """Model representing a configurable setting"""

    key: str
    name: str
    description: str
    type: SettingType
    category: SettingCategory
    visibility: SettingVisibility
    default_value: Any
    options: Optional[List[Any]] = None  # For OPTION type
    min_value: Optional[float] = None    # For NUMBER type
    max_value: Optional[float] = None    # For NUMBER type
    component_name: Optional[str] = None  # Related component name


class SettingsMenuSettings(BaseSettings):
    """Settings for the Settings Menu component"""

    enabled: bool = False
    use_web_app: bool = False  # Whether to use Telegram Web App
    web_app_url: str = ""      # URL for the settings web app
    command_name: str = "settings"  # Command to open settings
    admin_command_name: str = "admin_settings"  # Command for admin settings

    class Config:
        env_prefix = "BOTSPOT_SETTINGS_MENU_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# ---------------------------------------------
# endregion Settings Types and Classes
# ---------------------------------------------


# ---------------------------------------------
# region FSM States
# ---------------------------------------------


class SettingsStates(StatesGroup):
    """States for settings menu navigation"""

    main_menu = State()               # Main menu (admin or user)
    category_selection = State()      # Selecting a category
    setting_selection = State()       # Selecting a specific setting
    boolean_setting = State()         # Toggling boolean setting
    option_setting = State()          # Selecting from options
    text_input = State()              # Entering text value
    number_input = State()            # Entering numeric value
    model_selection = State()         # Special case for model selection
    confirmation = State()            # Confirming changes


# ---------------------------------------------
# endregion FSM States
# ---------------------------------------------


# ---------------------------------------------
# region Settings Registry
# ---------------------------------------------


class SettingsRegistry:
    """Registry for all available settings in the system"""

    def __init__(self):
        self.admin_settings: Dict[str, Setting] = {}
        self.user_settings: Dict[str, Setting] = {}
        self._initialize_default_settings()

    def _initialize_default_settings(self):
        """Initialize default settings for admin and user"""
        # Admin settings - primarily for components
        self._register_admin_setting(
            Setting(
                key="llm_provider_model",
                name="Default LLM Model",
                description="Default model to use for LLM requests",
                type=SettingType.OPTION,
                category=SettingCategory.MODELS,
                visibility=SettingVisibility.ADMIN,
                default_value="claude-3.7",
                options=[
                    "claude-3.7", "claude-3-haiku", "claude-3-sonnet", "claude-3-opus",
                    "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "gemini-pro", "gemini-1.5-pro"
                ],
                component_name="llm_provider"
            )
        )
        
        self._register_admin_setting(
            Setting(
                key="llm_provider_temperature",
                name="LLM Temperature",
                description="Temperature parameter for LLM requests (0.0-1.0)",
                type=SettingType.NUMBER,
                category=SettingCategory.MODELS,
                visibility=SettingVisibility.ADMIN,
                default_value=0.7,
                min_value=0.0,
                max_value=1.0,
                component_name="llm_provider"
            )
        )
        
        self._register_admin_setting(
            Setting(
                key="llm_provider_allow_everyone",
                name="Allow Everyone to Use LLM",
                description="Allow all users to use LLM features, not just admins and friends",
                type=SettingType.BOOLEAN,
                category=SettingCategory.PRIVACY,
                visibility=SettingVisibility.ADMIN,
                default_value=False,
                component_name="llm_provider"
            )
        )
        
        # User settings
        self._register_user_setting(
            Setting(
                key="notifications_enabled",
                name="Enable Notifications",
                description="Receive notifications from the bot",
                type=SettingType.BOOLEAN,
                category=SettingCategory.NOTIFICATIONS,
                visibility=SettingVisibility.USER,
                default_value=True
            )
        )
        
        self._register_user_setting(
            Setting(
                key="user_preferred_language",
                name="Preferred Language",
                description="Language for bot responses",
                type=SettingType.OPTION,
                category=SettingCategory.APPEARANCE,
                visibility=SettingVisibility.USER,
                default_value="en",
                options=["en", "ru", "es", "fr", "de"]
            )
        )

    def _register_admin_setting(self, setting: Setting):
        """Register an admin setting"""
        self.admin_settings[setting.key] = setting

    def _register_user_setting(self, setting: Setting):
        """Register a user setting"""
        self.user_settings[setting.key] = setting
    
    def register_setting(self, setting: Setting):
        """Register a setting based on its visibility"""
        if setting.visibility == SettingVisibility.ADMIN:
            self._register_admin_setting(setting)
        else:
            self._register_user_setting(setting)

    def get_admin_settings(self, category: Optional[SettingCategory] = None) -> Dict[str, Setting]:
        """Get admin settings, optionally filtered by category"""
        if category is None:
            return self.admin_settings
        
        return {k: v for k, v in self.admin_settings.items() if v.category == category}
    
    def get_user_settings(self, category: Optional[SettingCategory] = None) -> Dict[str, Setting]:
        """Get user settings, optionally filtered by category"""
        if category is None:
            return self.user_settings
        
        return {k: v for k, v in self.user_settings.items() if v.category == category}
    
    def get_setting(self, key: str) -> Optional[Setting]:
        """Get a setting by key"""
        if key in self.admin_settings:
            return self.admin_settings[key]
        if key in self.user_settings:
            return self.user_settings[key]
        return None
    
    def get_categories(self, is_admin: bool = False) -> List[SettingCategory]:
        """Get unique categories for admin or user settings"""
        settings = self.admin_settings if is_admin else self.user_settings
        return list({s.category for s in settings.values()})


# Global registry instance
settings_registry = SettingsRegistry()


# ---------------------------------------------
# endregion Settings Registry
# ---------------------------------------------


# ---------------------------------------------
# region Settings Storage
# ---------------------------------------------


class SettingsManager:
    """Manage storage and retrieval of setting values"""

    def __init__(self):
        self.registry = settings_registry
        self._admin_values: Dict[str, Any] = {}  # In-memory cache for admin settings
    
    async def get_admin_setting(self, key: str) -> Any:
        """Get admin setting value"""
        from botspot.core.dependency_manager import get_dependency_manager
        
        deps = get_dependency_manager()
        setting = self.registry.get_setting(key)
        
        if not setting:
            return None
        
        # Check if component-specific setting
        if setting.component_name:
            # Special handling for components
            if setting.component_name == "llm_provider":
                if key == "llm_provider_model":
                    return deps.botspot_settings.llm_provider.default_model
                elif key == "llm_provider_temperature":
                    return deps.botspot_settings.llm_provider.default_temperature
                elif key == "llm_provider_allow_everyone":
                    return deps.botspot_settings.llm_provider.allow_everyone
            
            # Add other components as needed
        
        # Use in-memory cache for other admin settings
        if key in self._admin_values:
            return self._admin_values[key]
        
        # Return default if not found
        return setting.default_value
    
    async def set_admin_setting(self, key: str, value: Any) -> bool:
        """Set admin setting value"""
        from botspot.core.dependency_manager import get_dependency_manager
        
        deps = get_dependency_manager()
        setting = self.registry.get_setting(key)
        
        if not setting:
            return False
        
        # Check if component-specific setting
        if setting.component_name:
            # Special handling for components
            if setting.component_name == "llm_provider":
                if key == "llm_provider_model":
                    deps.botspot_settings.llm_provider.default_model = value
                    deps.llm_provider.settings.default_model = value
                    return True
                elif key == "llm_provider_temperature":
                    deps.botspot_settings.llm_provider.default_temperature = value
                    deps.llm_provider.settings.default_temperature = value
                    return True
                elif key == "llm_provider_allow_everyone":
                    deps.botspot_settings.llm_provider.allow_everyone = value
                    deps.llm_provider.settings.allow_everyone = value
                    return True
            
            # Add other components as needed
        
        # Use in-memory cache for other admin settings
        self._admin_values[key] = value
        return True
    
    async def get_user_setting(self, user_id: int, key: str) -> Any:
        """Get user setting value"""
        user_manager = get_user_manager()
        user = await user_manager.get_user(user_id)
        
        if not user:
            setting = self.registry.get_setting(key)
            return setting.default_value if setting else None
        
        # Use custom fields for user settings
        # First check if user has settings attribute
        if not hasattr(user, "settings") or not user.settings:
            setting = self.registry.get_setting(key)
            return setting.default_value if setting else None
        
        # Check if key exists in user settings
        if key in user.settings:
            return user.settings[key]
        
        # Return default if not found
        setting = self.registry.get_setting(key)
        return setting.default_value if setting else None
    
    async def set_user_setting(self, user_id: int, key: str, value: Any) -> bool:
        """Set user setting value"""
        user_manager = get_user_manager()
        user = await user_manager.get_user(user_id)
        
        if not user:
            return False
        
        # Initialize settings if not exists
        if not hasattr(user, "settings"):
            # Add settings field to user model if not exists
            user_dict = user.model_dump()
            user_dict["settings"] = {}
            user = User(**user_dict)
        
        # Create empty settings dict if None
        if user.settings is None:
            user.settings = {}
        
        # Set the value
        user.settings[key] = value
        
        # Update user in database
        await user_manager.update_user(user_id, "settings", user.settings)
        return True


# Global settings manager instance
settings_manager = SettingsManager()


# ---------------------------------------------
# endregion Settings Storage
# ---------------------------------------------


# ---------------------------------------------
# region Keyboard Builders
# ---------------------------------------------


def build_main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Build main menu keyboard for settings"""
    categories = settings_registry.get_categories(is_admin=is_admin)
    keyboard = []
    
    # Add category buttons
    for category in categories:
        keyboard.append([
            InlineKeyboardButton(
                text=f"📋 {category.name.capitalize()}",
                callback_data=f"settings_category_{category.value}"
            )
        ])
    
    # Add back button
    keyboard.append([
        InlineKeyboardButton(text="❌ Close", callback_data="settings_close")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_category_keyboard(category: SettingCategory, is_admin: bool = False) -> InlineKeyboardMarkup:
    """Build keyboard for settings in a category"""
    if is_admin:
        settings = settings_registry.get_admin_settings(category)
    else:
        settings = settings_registry.get_user_settings(category)
    
    keyboard = []
    
    # Add setting buttons
    for key, setting in settings.items():
        keyboard.append([
            InlineKeyboardButton(
                text=f"{setting.name}",
                callback_data=f"settings_select_{key}"
            )
        ])
    
    # Add back button
    keyboard.append([
        InlineKeyboardButton(text="⬅️ Back", callback_data="settings_back_to_main")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_boolean_setting_keyboard(key: str, current_value: bool) -> InlineKeyboardMarkup:
    """Build keyboard for boolean setting"""
    keyboard = [
        [
            InlineKeyboardButton(
                text=f"✅ Enabled" if current_value else "Enabled",
                callback_data=f"settings_bool_{key}_true"
            ),
            InlineKeyboardButton(
                text=f"❌ Disabled" if not current_value else "Disabled",
                callback_data=f"settings_bool_{key}_false"
            )
        ],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="settings_back_to_category")
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_option_setting_keyboard(key: str, options: List[Any], current_value: Any) -> InlineKeyboardMarkup:
    """Build keyboard for option setting"""
    keyboard = []
    
    # Add option buttons
    for option in options:
        option_text = str(option)
        is_selected = option == current_value
        keyboard.append([
            InlineKeyboardButton(
                text=f"✅ {option_text}" if is_selected else option_text,
                callback_data=f"settings_option_{key}_{option}"
            )
        ])
    
    # Add back button
    keyboard.append([
        InlineKeyboardButton(text="⬅️ Back", callback_data="settings_back_to_category")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ---------------------------------------------
# endregion Keyboard Builders
# ---------------------------------------------


# ---------------------------------------------
# region Handlers
# ---------------------------------------------


async def settings_command(message: Message, state: FSMContext):
    """Handler for /settings command"""
    # Reset state
    await state.clear()
    
    # Check if user is admin for admin settings
    is_admin = await AdminFilter()(message)
    
    # Store admin flag in state data
    await state.update_data(is_admin=is_admin)
    
    # Build and send main menu
    keyboard = build_main_menu_keyboard(is_admin=is_admin)
    
    title = "🔧 Admin Settings" if is_admin else "⚙️ User Settings"
    text = (
        f"{title}\n\n"
        f"Select a category to configure:"
    )
    
    await message.answer(text, reply_markup=keyboard)
    await state.set_state(SettingsStates.main_menu)


async def admin_settings_command(message: Message, state: FSMContext):
    """Handler for /admin_settings command (admin only)"""
    # Clear previous state
    await state.clear()
    
    # Store admin flag in state data (always true for this command)
    await state.update_data(is_admin=True)
    
    # Build and send admin main menu
    keyboard = build_main_menu_keyboard(is_admin=True)
    
    text = (
        "🔧 Admin Settings\n\n"
        "Select a category to configure:"
    )
    
    await message.answer(text, reply_markup=keyboard)
    await state.set_state(SettingsStates.main_menu)


async def category_callback(query: CallbackQuery, state: FSMContext):
    """Handle category selection"""
    await query.answer()
    
    # Get category from callback data
    callback_data = query.data
    category_value = callback_data.replace("settings_category_", "")
    category = SettingCategory(category_value)
    
    # Store selected category in state
    state_data = await state.get_data()
    is_admin = state_data.get("is_admin", False)
    
    await state.update_data(category=category_value)
    
    # Build and send category keyboard
    keyboard = build_category_keyboard(category, is_admin=is_admin)
    
    text = (
        f"⚙️ {category.name.capitalize()} Settings\n\n"
        f"Select a setting to configure:"
    )
    
    await query.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(SettingsStates.category_selection)


async def setting_select_callback(query: CallbackQuery, state: FSMContext):
    """Handle setting selection"""
    await query.answer()
    
    # Get setting key from callback data
    callback_data = query.data
    setting_key = callback_data.replace("settings_select_", "")
    
    # Get setting details
    setting = settings_registry.get_setting(setting_key)
    if not setting:
        await query.message.edit_text("Setting not found.")
        return
    
    # Store setting key in state
    state_data = await state.get_data()
    is_admin = state_data.get("is_admin", False)
    
    await state.update_data(setting_key=setting_key)
    
    # Get current value
    if is_admin:
        current_value = await settings_manager.get_admin_setting(setting_key)
    else:
        user_id = query.from_user.id
        current_value = await settings_manager.get_user_setting(user_id, setting_key)
    
    if setting.type == SettingType.BOOLEAN:
        # Build boolean keyboard
        keyboard = build_boolean_setting_keyboard(setting_key, current_value)
        
        text = (
            f"⚙️ {setting.name}\n\n"
            f"{setting.description}\n\n"
            f"Current value: {'Enabled' if current_value else 'Disabled'}"
        )
        
        await query.message.edit_text(text, reply_markup=keyboard)
        await state.set_state(SettingsStates.boolean_setting)
    
    elif setting.type == SettingType.OPTION:
        # Build option keyboard
        keyboard = build_option_setting_keyboard(setting_key, setting.options, current_value)
        
        text = (
            f"⚙️ {setting.name}\n\n"
            f"{setting.description}\n\n"
            f"Current value: {current_value}"
        )
        
        await query.message.edit_text(text, reply_markup=keyboard)
        await state.set_state(SettingsStates.option_setting)
    
    elif setting.type == SettingType.TEXT:
        text = (
            f"⚙️ {setting.name}\n\n"
            f"{setting.description}\n\n"
            f"Current value: {current_value}\n\n"
            f"Please enter a new value or click Back to cancel:"
        )
        
        # Add back button
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="settings_back_to_category")]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard)
        await state.set_state(SettingsStates.text_input)
    
    elif setting.type == SettingType.NUMBER:
        text = (
            f"⚙️ {setting.name}\n\n"
            f"{setting.description}\n\n"
            f"Current value: {current_value}\n\n"
            f"Please enter a new value between {setting.min_value} and {setting.max_value}, "
            f"or click Back to cancel:"
        )
        
        # Add back button
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="settings_back_to_category")]
        ])
        
        await query.message.edit_text(text, reply_markup=keyboard)
        await state.set_state(SettingsStates.number_input)
    
    elif setting.type == SettingType.MODEL:
        # Special case for model selection
        # Similar to option but with model-specific options
        # This would typically use a dedicated handler or keyboard builder
        pass


async def boolean_setting_callback(query: CallbackQuery, state: FSMContext):
    """Handle boolean setting changes"""
    await query.answer()
    
    # Parse callback data: format is "settings_bool_{key}_{value}"
    parts = query.data.split("_")
    setting_key = parts[2]
    new_value = parts[3] == "true"
    
    # Get state data
    state_data = await state.get_data()
    is_admin = state_data.get("is_admin", False)
    
    # Update setting
    if is_admin:
        success = await settings_manager.set_admin_setting(setting_key, new_value)
    else:
        user_id = query.from_user.id
        success = await settings_manager.set_user_setting(user_id, setting_key, new_value)
    
    if not success:
        await query.message.edit_text("Failed to update setting.")
        return
    
    # Get setting details
    setting = settings_registry.get_setting(setting_key)
    
    # Update keyboard with new value
    keyboard = build_boolean_setting_keyboard(setting_key, new_value)
    
    text = (
        f"⚙️ {setting.name}\n\n"
        f"{setting.description}\n\n"
        f"Current value: {'Enabled' if new_value else 'Disabled'}\n\n"
        f"✅ Setting updated!"
    )
    
    await query.message.edit_text(text, reply_markup=keyboard)


async def option_setting_callback(query: CallbackQuery, state: FSMContext):
    """Handle option setting changes"""
    await query.answer()
    
    # Parse callback data: format is "settings_option_{key}_{value}"
    parts = query.data.split("_")
    setting_key = parts[2]
    new_value = parts[3]  # This might need conversion depending on option type
    
    # Get setting details
    setting = settings_registry.get_setting(setting_key)
    
    # Convert value to correct type if needed
    if setting and setting.options:
        # Find matching option by string representation
        for option in setting.options:
            if str(option) == new_value:
                new_value = option
                break
    
    # Get state data
    state_data = await state.get_data()
    is_admin = state_data.get("is_admin", False)
    
    # Update setting
    if is_admin:
        success = await settings_manager.set_admin_setting(setting_key, new_value)
    else:
        user_id = query.from_user.id
        success = await settings_manager.set_user_setting(user_id, setting_key, new_value)
    
    if not success:
        await query.message.edit_text("Failed to update setting.")
        return
    
    # Update keyboard with new value
    keyboard = build_option_setting_keyboard(setting_key, setting.options, new_value)
    
    text = (
        f"⚙️ {setting.name}\n\n"
        f"{setting.description}\n\n"
        f"Current value: {new_value}\n\n"
        f"✅ Setting updated!"
    )
    
    await query.message.edit_text(text, reply_markup=keyboard)


async def text_input_handler(message: Message, state: FSMContext):
    """Handle text input for text settings"""
    # Get state data
    state_data = await state.get_data()
    setting_key = state_data.get("setting_key")
    is_admin = state_data.get("is_admin", False)
    
    # Get setting details
    setting = settings_registry.get_setting(setting_key)
    if not setting:
        await message.answer("Setting not found.")
        return
    
    # Get new value from message
    new_value = message.text.strip()
    
    # Update setting
    if is_admin:
        success = await settings_manager.set_admin_setting(setting_key, new_value)
    else:
        user_id = message.from_user.id
        success = await settings_manager.set_user_setting(user_id, setting_key, new_value)
    
    if not success:
        await message.answer("Failed to update setting.")
        return
    
    # Send confirmation
    text = (
        f"⚙️ {setting.name}\n\n"
        f"New value: {new_value}\n\n"
        f"✅ Setting updated!"
    )
    
    # Add back buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back to Category", callback_data="settings_back_to_category")],
        [InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="settings_back_to_main")]
    ])
    
    await message.answer(text, reply_markup=keyboard)


async def number_input_handler(message: Message, state: FSMContext):
    """Handle numeric input for number settings"""
    # Get state data
    state_data = await state.get_data()
    setting_key = state_data.get("setting_key")
    is_admin = state_data.get("is_admin", False)
    
    # Get setting details
    setting = settings_registry.get_setting(setting_key)
    if not setting:
        await message.answer("Setting not found.")
        return
    
    # Try to parse number from input
    try:
        new_value = float(message.text.strip())
        
        # Validate range if min/max are set
        if setting.min_value is not None and new_value < setting.min_value:
            await message.answer(f"Value must be at least {setting.min_value}. Please try again.")
            return
        
        if setting.max_value is not None and new_value > setting.max_value:
            await message.answer(f"Value must be at most {setting.max_value}. Please try again.")
            return
    except ValueError:
        await message.answer("Please enter a valid number. Try again.")
        return
    
    # Update setting
    if is_admin:
        success = await settings_manager.set_admin_setting(setting_key, new_value)
    else:
        user_id = message.from_user.id
        success = await settings_manager.set_user_setting(user_id, setting_key, new_value)
    
    if not success:
        await message.answer("Failed to update setting.")
        return
    
    # Send confirmation
    text = (
        f"⚙️ {setting.name}\n\n"
        f"New value: {new_value}\n\n"
        f"✅ Setting updated!"
    )
    
    # Add back buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back to Category", callback_data="settings_back_to_category")],
        [InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="settings_back_to_main")]
    ])
    
    await message.answer(text, reply_markup=keyboard)


async def back_to_main_callback(query: CallbackQuery, state: FSMContext):
    """Handle back to main menu button"""
    await query.answer()
    
    # Get state data
    state_data = await state.get_data()
    is_admin = state_data.get("is_admin", False)
    
    # Build and send main menu
    keyboard = build_main_menu_keyboard(is_admin=is_admin)
    
    title = "🔧 Admin Settings" if is_admin else "⚙️ User Settings"
    text = (
        f"{title}\n\n"
        f"Select a category to configure:"
    )
    
    await query.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(SettingsStates.main_menu)


async def back_to_category_callback(query: CallbackQuery, state: FSMContext):
    """Handle back to category button"""
    await query.answer()
    
    # Get state data
    state_data = await state.get_data()
    category_value = state_data.get("category")
    is_admin = state_data.get("is_admin", False)
    
    if not category_value:
        # Fallback to main menu if category not found
        await back_to_main_callback(query, state)
        return
    
    category = SettingCategory(category_value)
    
    # Build and send category keyboard
    keyboard = build_category_keyboard(category, is_admin=is_admin)
    
    text = (
        f"⚙️ {category.name.capitalize()} Settings\n\n"
        f"Select a setting to configure:"
    )
    
    await query.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(SettingsStates.category_selection)


async def close_settings_callback(query: CallbackQuery, state: FSMContext):
    """Handle close settings button"""
    await query.answer()
    await query.message.delete()
    await state.clear()


# ---------------------------------------------
# endregion Handlers
# ---------------------------------------------


# ---------------------------------------------
# region Dispatcher Setup
# ---------------------------------------------


def setup_dispatcher(dp: Dispatcher, settings: SettingsMenuSettings = None):
    """Set up the dispatcher with the settings menu component"""
    if settings is None:
        settings = SettingsMenuSettings()
    
    if not settings.enabled:
        logger.info("Settings Menu component is disabled")
        return
    
    logger.info("Setting up Settings Menu component")
    
    # Create router
    router = Router(name="settings_menu")
    
    # Register commands
    from botspot import commands_menu
    from botspot.commands_menu import Visibility
    
    # User settings command
    @commands_menu.botspot_command(settings.command_name, "Configure your bot settings")
    @router.message(Command(settings.command_name))
    async def settings_cmd(message: Message, state: FSMContext):
        await settings_command(message, state)
    
    # Admin settings command (admin-only)
    @commands_menu.botspot_command(settings.admin_command_name, 
                                  "Configure admin settings", 
                                  Visibility.ADMIN_ONLY)
    @router.message(Command(settings.admin_command_name))
    @router.message(AdminFilter())
    async def admin_settings_cmd(message: Message, state: FSMContext):
        await admin_settings_command(message, state)
    
    # Register callback handlers
    router.callback_query.register(category_callback, 
                                  F.data.startswith("settings_category_"))
    
    router.callback_query.register(setting_select_callback, 
                                  F.data.startswith("settings_select_"))
    
    router.callback_query.register(boolean_setting_callback, 
                                  F.data.startswith("settings_bool_"))
    
    router.callback_query.register(option_setting_callback, 
                                  F.data.startswith("settings_option_"))
    
    router.callback_query.register(back_to_main_callback, 
                                  F.data == "settings_back_to_main")
    
    router.callback_query.register(back_to_category_callback, 
                                  F.data == "settings_back_to_category")
    
    router.callback_query.register(close_settings_callback, 
                                  F.data == "settings_close")
    
    # Register message handlers for text/number input
    router.message.register(text_input_handler, SettingsStates.text_input)
    router.message.register(number_input_handler, SettingsStates.number_input)
    
    # Include router in dispatcher
    dp.include_router(router)
    
    return dp


def initialize(settings: SettingsMenuSettings):
    """Initialize the settings menu component"""
    if not settings.enabled:
        logger.info("Settings Menu component is disabled")
        return None
    
    logger.info("Initializing Settings Menu component")
    return settings_registry


# ---------------------------------------------
# endregion Dispatcher Setup
# ---------------------------------------------


# ---------------------------------------------
# region Utils
# ---------------------------------------------


def register_component_setting(
    component_name: str,
    key: str,
    name: str,
    description: str,
    setting_type: SettingType,
    category: SettingCategory = SettingCategory.ADVANCED,
    visibility: SettingVisibility = SettingVisibility.ADMIN,
    default_value: Any = None,
    options: Optional[List[Any]] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> None:
    """Register a setting for a component"""
    setting = Setting(
        key=key,
        name=name,
        description=description,
        type=setting_type,
        category=category,
        visibility=visibility,
        default_value=default_value,
        options=options,
        min_value=min_value,
        max_value=max_value,
        component_name=component_name
    )
    
    settings_registry.register_setting(setting)


def get_settings_registry():
    """Get the global settings registry"""
    return settings_registry


def get_settings_manager():
    """Get the global settings manager"""
    return settings_manager


# ---------------------------------------------
# endregion Utils
# ---------------------------------------------