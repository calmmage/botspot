"""
Telethon Manager component for managing Telegram user clients.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from aiogram import Dispatcher
from pydantic import SecretStr
from pydantic_settings import BaseSettings

from botspot.components.features.user_interactions import ask_user
from botspot.utils.internal import get_logger
from botspot.utils.send_safe import send_safe

if TYPE_CHECKING:
    from telethon import TelegramClient

logger = get_logger()


class TelethonManagerSettings(BaseSettings):
    enabled: bool = False
    api_id: Optional[int] = None
    api_hash: Optional[SecretStr] = None
    sessions_dir: str = "sessions"
    auto_auth: bool = True  # Whether to automatically trigger auth when client is missing

    class Config:
        env_prefix = "BOTSPOT_TELETHON_MANAGER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class TelethonManager:
    def __init__(self, api_id: int, api_hash: str, sessions_dir: Path, auto_auth: bool = True):
        self.api_id = api_id
        self.api_hash = api_hash
        self.sessions_dir = sessions_dir
        self.auto_auth = auto_auth
        self.sessions_dir.mkdir(exist_ok=True)
        self.clients: Dict[int, "TelegramClient"] = {}
        logger.info(f"TelethonManager initialized with sessions dir: {sessions_dir}")

    async def init_session(self, user_id: int) -> "TelegramClient":
        """Initialize and verify a session for user_id"""
        from telethon import TelegramClient

        session_key = self.sessions_dir / f"user_{user_id}"
        session_file = session_key.with_suffix(".session")
        logger.info(f"Initializing session for user {user_id} from {session_file}")

        if not session_file.exists():
            logger.info(f"No session file found for user {user_id}")
            return None

        client = TelegramClient(str(session_key), self.api_id, self.api_hash)
        try:
            await client.connect()

            is_authorized = await client.is_user_authorized()
            logger.info(f"Session authorization check for user {user_id}: {is_authorized}")

            if is_authorized:
                self.clients[user_id] = client
                return client

            logger.info(f"Session exists but not authorized for user {user_id}")
            # todo: delete the file here and now - so that next attempt will try again..
            return None

        except Exception as e:
            logger.warning(f"Failed to initialize session for user {user_id}: {e}")
            return None

    async def init_all_sessions(self):
        """Initialize all existing sessions from disk"""
        logger.info("Initializing all sessions...")
        session_files = list(self.sessions_dir.glob("user_*"))
        logger.info(f"Found {len(session_files)} session files: {session_files}")

        for session_file in session_files:
            try:
                user_id = int(session_file.stem.split("_")[1])
                logger.info(f"Found session file for user {user_id}")
                await self.init_session(user_id)
            except Exception as e:
                logger.warning(f"Failed to init session from {session_file}: {e}")

    async def get_client(self, user_id: int, state=None) -> "TelegramClient":
        """
        Get or initialize client for user_id.
        If auto_auth is True and state is provided, will trigger authentication if client is missing.
        """
        if user_id in self.clients:
            return self.clients[user_id]

        client = await self.init_session(user_id)
        if client:
            return client

        # If we get here, no client exists or it's not authorized
        if self.auto_auth and state:
            logger.info(f"Auto-authenticating client for user {user_id}")
            return await self.setup_client(user_id, state)

        return None

    async def disconnect_all(self):
        """Disconnect all clients"""
        for client in self.clients.values():
            await client.disconnect()
        self.clients.clear()

    async def setup_client(self, user_id: int, state, force: bool = False) -> "TelegramClient":
        """
        Setup Telethon client for a specific user

        Args:
            user_id: Telegram user ID (also used as chat_id for messaging)
            state: FSM state for ask_user
            force: If True, will delete existing session and create new one

        Returns:
            TelegramClient if setup was successful, None otherwise
        """
        from telethon import TelegramClient

        # Check if user already has an authenticated session
        if not force:
            existing_client = await self.get_client(user_id)
            if existing_client:
                await send_safe(
                    user_id,
                    "You already have an active Telethon session! "
                    "Use /setup_telethon_force to create a new one.",
                )
                return existing_client

        # Create new client
        session_key = self.sessions_dir / f"user_{user_id}"
        session_file = session_key.with_suffix(".session")
        if session_file.exists():
            session_file.unlink()

        client = TelegramClient(str(session_key), self.api_id, self.api_hash)

        try:
            await client.connect()

            # Ask for phone number
            phone = await ask_user(
                user_id,
                "Please enter your phone number (including country code, e.g., +1234567890):",
                state,
                timeout=60.0,
            )

            if not phone:
                await send_safe(user_id, "Setup cancelled - no phone number provided.")
                return None

            # Send code request
            send_code_result = await client.send_code_request(phone)

            # Ask for verification code
            code = await ask_user(
                user_id,
                "Please enter MODIFIED verification code as follows: YOUR CODE splitted with spaces e.g '21694' -> '2 1 6 9 4' or telegram WILL BLOCK IT",
                state,
                timeout=300.0,
                cleanup=True,
            )

            if not code:
                await send_safe(user_id, "Setup cancelled - no verification code provided.")
                return None

            if " " not in code.strip():
                await send_safe(
                    user_id,
                    "Setup cancelled - YOU DID NOT split the code with spaces like this: '2 1 6 9 4'",
                )
                return None

            code = code.replace(" ", "")

            try:
                # Try to sign in with the code
                await client.sign_in(phone, code, phone_code_hash=send_code_result.phone_code_hash)
            except Exception as e:
                if "password" in str(e).lower():
                    # 2FA is enabled, ask for password
                    password = await ask_user(
                        user_id,
                        "Two-factor authentication is enabled. Please enter your 2FA password:",
                        state,
                        timeout=300.0,
                        cleanup=True,
                    )

                    if not password:
                        await send_safe(user_id, "Setup cancelled - no password provided.")
                        return None

                    password = password.replace(" ", "")

                    # Sign in with password
                    await client.sign_in(password=password)
                else:
                    raise

            # If we got here, authentication was successful
            self.clients[user_id] = client
            await send_safe(
                user_id,
                "Successfully set up Telethon client! The session is saved and ready to use.",
            )
            return client

        except Exception as e:
            await send_safe(user_id, f"Error during setup: {str(e)}")
            if session_file.exists():
                session_file.unlink()
            return None


def initialize(settings: TelethonManagerSettings) -> TelethonManager:
    """Initialize TelethonManager with settings"""
    # Check that Telethon is installed
    import telethon

    assert telethon

    sessions_dir = Path(settings.sessions_dir)
    return TelethonManager(
        settings.api_id,
        settings.api_hash.get_secret_value(),
        sessions_dir,
        settings.auto_auth,
    )


def setup_dispatcher(dp: Dispatcher) -> None:
    """Setup dispatcher with TelethonManager handlers"""
    from aiogram.filters import Command
    from aiogram.fsm.context import FSMContext
    from aiogram.types import Message

    from botspot.components.settings.bot_commands_menu import add_command
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    telethon_manager = deps.telethon_manager

    @add_command("setup_telethon", "Setup Telethon user client", visibility="hidden")
    @dp.message(Command("setup_telethon"))
    async def setup_telethon_command(message: Message, state: FSMContext) -> None:
        await telethon_manager.setup_client(message.from_user.id, state=state)

    @add_command("setup_telethon_force", "Force new Telethon client setup", visibility="hidden")
    @dp.message(Command("setup_telethon_force"))
    async def setup_telethon_force_command(message: Message, state: FSMContext) -> None:
        await telethon_manager.setup_client(message.from_user.id, state=state, force=True)

    @add_command("check_telethon", "Check if Telethon client is active", visibility="hidden")
    @dp.message(Command("check_telethon"))
    async def check_telethon_handler(message: Message) -> None:
        """Check if user has an active Telethon client"""
        client = await telethon_manager.get_client(message.from_user.id)
        if client and await client.is_user_authorized():
            me = await client.get_me()
            await message.reply(f"Active Telethon session found for {me.first_name}!")
        else:
            await message.reply(
                "No active Telethon session found. Use /setup_telethon to create one."
            )
