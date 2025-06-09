"""Contact Manager component for managing user contacts."""

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from aiogram import Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger
from botspot import commands_menu
from botspot.components.new.queue_manager import QueueItem, get_queue_manager

logger = get_logger()


# ---------------------------------------------
# region Settings and Model Definitions
# ---------------------------------------------

class ContactManagerSettings(BaseSettings):
    enabled: bool = False
    collection: str = "contacts"
    message_parser_enabled: bool = True
    random_contact_enabled: bool = True
    allow_everyone: bool = False  # If False, only friends and admins can use

    class Config:
        env_prefix = "BOTSPOT_CONTACT_MANAGER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection  # noqa: F401
    from botspot.commands_menu import Visibility
    from botspot.components.new.queue_manager import QueueManager


class ContactItem(QueueItem):
    """Contact information model."""

    name: str
    user_id: Optional[int] = None  # Telegram user ID if applicable
    phone: Optional[str] = None  # Phone number
    email: Optional[str] = None  # Email address
    telegram: Optional[str] = None  # Telegram username
    birthday: Optional[date] = None  # Birthday
    notes: Optional[str] = None  # Any additional notes
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    owner_id: Optional[int] = None  # Who added this contact

    @property
    def display_info(self) -> str:
        """Return formatted contact information."""
        parts = [f"📇 **{self.name}**"]

        if self.phone:
            parts.append(f"📱 Phone: {self.phone}")
        if self.email:
            parts.append(f"📧 Email: {self.email}")
        if self.telegram:
            username = self.telegram.strip('@')
            parts.append(f"📨 Telegram: @{username}")
        if self.birthday:
            parts.append(f"🎂 Birthday: {self.birthday.strftime('%d %B')}")
        if self.notes:
            parts.append(f"📝 Notes: {self.notes}")
        if self.user_id:
            parts.append(f"👤 User ID: {self.user_id}")
        if self.owner_id:
            parts.append(f"👤 Owner ID: {self.owner_id}")

        return "\n".join(parts)


# ---------------------------------------------
# endregion Settings and Model Definitions
# ---------------------------------------------


# ---------------------------------------------
# region Contact Manager Implementation
# ---------------------------------------------

# TODO: change the way this works, make a collection of Queues, one queue per Owner_id.
# Currently its only viable for personal use(i.e. only one user per bot)
class ContactManager:
    """Manager for user contacts."""

    def __init__(
            self,
            settings: ContactManagerSettings,
            queue_manager: Optional["QueueManager"] = None,
    ):
        """Initialize contact manager with settings."""
        self.settings = settings
        self._queue_manager = queue_manager
        self.queue = None

    @classmethod
    async def create(
            cls,
            settings: ContactManagerSettings,
            queue_manager: Optional["QueueManager"] = None,
    ) -> "ContactManager":
        """Create a new instance of ContactManager with async initialization."""
        instance = cls(settings, queue_manager)
        instance._queue_manager = queue_manager or await get_queue_manager()
        instance.queue = instance._queue_manager.create_queue(
            key=instance.settings.collection,
            item_model=ContactItem,
            use_timestamp=True,
            use_priority=False,
            use_done=False,
        )
        return instance

    async def add_contact(self, contact: ContactItem, owner_id: Optional[int] = None) -> bool:
        """Add a new contact to the queue."""
        try:
            if owner_id:
                contact.owner_id = owner_id
            await self.queue.add_item(contact, user_id=owner_id)
            logger.info(f"Added contact: {contact.name}")
            return True
        except Exception as e:
            logger.error(f"Error adding contact: {e}")
            from botspot.core.errors import ContactDataError
            raise ContactDataError("Failed to add contact") from e

    async def update_contact(
            self, contact_id: str, data: Dict[str, Any], owner_id: Optional[int] = None
    ) -> bool:
        """Update an existing contact."""
        try:
            # Get the current contact
            contact = await self.get_contact_by_id(contact_id, owner_id)
            if not contact:
                from botspot.core.errors import ContactDataError
                raise ContactDataError("Contact not found")

            # Update fields
            for key, value in data.items():
                if hasattr(contact, key):
                    setattr(contact, key, value)
            contact.updated_at = datetime.now(timezone.utc)

            # Update in queue
            result = await self.queue.update_record(contact_id, contact.model_dump())
            if not result:
                from botspot.core.errors import ContactDataError
                raise ContactDataError("Failed to update contact")
            return True
        except Exception as e:
            logger.error(f"Error updating contact: {e}")
            from botspot.core.errors import ContactDataError
            raise ContactDataError("Failed to update contact") from e

    async def delete_contact(self, contact_id: str, owner_id: Optional[int] = None) -> bool:
        """Delete a contact from the queue."""
        try:
            result = await self.queue.delete_record(contact_id, user_id=owner_id)
            if not result:
                from botspot.core.errors import ContactDataError
                raise ContactDataError("Contact not found or deletion failed")
            return True
        except Exception as e:
            logger.error(f"Error deleting contact: {e}")
            from botspot.core.errors import ContactDataError
            raise ContactDataError("Failed to delete contact") from e

    async def get_contact_by_id(
            self, contact_id: str, owner_id: Optional[int] = None
    ) -> Optional[ContactItem]:
        """Get a contact by its ID."""
        try:
            contact_data = await self.queue.find({"_id": contact_id}, user_id=owner_id)
            if not contact_data:
                return None
            return ContactItem(**contact_data)
        except Exception as e:
            logger.error(f"Error getting contact: {e}")
            from botspot.core.errors import ContactDataError
            raise ContactDataError("Failed to get contact") from e

    async def find_contacts(
            self,
            query: Dict[str, Any],
            limit: int = 10,
            owner_id: Optional[int] = None,
    ) -> List[ContactItem]:
        """Find contacts matching the given query."""
        try:
            contacts_data = await self.queue.find_many(
                query,
                limit=limit,
                user_id=owner_id
            )
            return [ContactItem(**contact) for contact in contacts_data]
        except Exception as e:
            logger.error(f"Error finding contacts: {e}")
            from botspot.core.errors import ContactDataError
            raise ContactDataError("Failed to find contacts") from e

    async def search_contacts(
            self,
            text: str,
            limit: int = 10,
            owner_id: Optional[int] = None,
    ) -> List[ContactItem]:
        """Search for contacts by name, email, etc."""
        try:
            # Create a query with $or for text matching across multiple fields
            query: Dict[str, Any] = {
                "$or": [
                    {"name": {"$regex": text, "$options": "i"}},
                    {"email": {"$regex": text, "$options": "i"}},
                    {"phone": {"$regex": text, "$options": "i"}},
                    {"telegram": {"$regex": text, "$options": "i"}},
                    {"notes": {"$regex": text, "$options": "i"}}
                ]
            }
            return await self.find_contacts(
                query,
                limit=limit,
                owner_id=owner_id
            )
        except Exception as e:
            logger.error(f"Error searching contacts: {e}")
            from botspot.core.errors import ContactDataError
            raise ContactDataError("Failed to search contacts") from e

    async def get_random_contact(
            self, owner_id: Optional[int] = None
    ) -> Optional[ContactItem]:
        """Get a random contact from the queue."""
        try:
            contact_data = await self.queue.get_random_record(user_id=owner_id)
            if not contact_data:
                return None
            return ContactItem(**contact_data)
        except Exception as e:
            logger.error(f"Error getting random contact: {e}")
            from botspot.core.errors import ContactDataError
            raise ContactDataError("Failed to get random contact") from e

    async def parse_contact_with_llm(
            self, text: str, owner_id: Optional[int] = None
    ) -> Optional[ContactItem]:
        """Parse contact information from text using LLM."""
        try:
            from botspot.utils.deps_getters import get_llm_provider

            llm = get_llm_provider()
            if not llm:
                from botspot.core.errors import ContactDataError
                raise ContactDataError("LLM provider not available")

            # System message for the LLM
            system_message = """
            You are a contact information parser. Extract contact details from the user's message.
            Return ONLY a valid JSON object with the following structure:
            {
                "name": "Person's name",
                "phone": "Phone number (if found)",
                "email": "Email (if found)",
                "telegram": "Telegram username (if found)",
                "birthday": "Birthday in YYYY-MM-DD format (if found)",
                "notes": "Any additional information",
                "owner_id": null
            }
            
            If a field is not found, set it to null.
            The name field is required - make your best guess if not explicit.
            """

            # Create a temporary model for parsing
            class TempContact(BaseModel):
                name: str
                phone: Optional[str] = None
                email: Optional[str] = None
                telegram: Optional[str] = None
                birthday: Optional[date] = None
                notes: Optional[str] = None
                owner_id: Optional[int] = None

            # Use structured output for better parsing
            temp_contact = await llm.aquery_llm_structured(
                prompt=text,
                output_schema=TempContact,
                user=owner_id,
                system_message=system_message,
                temperature=0.2,  # Lower temperature for more deterministic output
            )

            # Create a new dictionary with owner_id if provided
            contact_data = temp_contact.model_dump()
            if owner_id is not None:
                contact_data["owner_id"] = owner_id

            # Convert to ContactItem
            return ContactItem.model_validate(contact_data)
        except Exception as e:
            logger.error(f"Error parsing contact with LLM: {e}")
            from botspot.core.errors import ContactDataError
            raise ContactDataError("Failed to parse contact information") from e

    async def get_contacts_by_owner(
            self, owner_id: int, limit: int = 10
    ) -> List[ContactItem]:
        """Get all contacts owned by a specific user."""
        try:
            query = {"owner_id": owner_id}
            return await self.find_contacts(
                query,
                limit=limit,
                owner_id=owner_id
            )
        except Exception as e:
            logger.error(f"Error getting contacts by owner: {e}")
            from botspot.core.errors import ContactDataError
            raise ContactDataError("Failed to get contacts by owner") from e

    async def get_contacts_by_telegram(
            self, telegram: str, limit: int = 10
    ) -> List[ContactItem]:
        """Get contacts by Telegram username."""
        try:
            query = {"telegram": telegram}
            return await self.find_contacts(
                query,
                limit=limit,  # Already validated as int
            )
        except Exception as e:
            logger.error(f"Error getting contacts by telegram: {e}")
            from botspot.core.errors import ContactDataError
            raise ContactDataError("Failed to get contacts by telegram") from e

    async def get_contacts_by_phone(
            self, phone: str, limit: int = 10
    ) -> List[ContactItem]:
        """Get contacts by phone number."""
        try:
            query = {"phone": phone}
            return await self.find_contacts(
                query,
                limit=limit,  # Already validated as int
            )
        except Exception as e:
            logger.error(f"Error getting contacts by phone: {e}")
            from botspot.core.errors import ContactDataError
            raise ContactDataError("Failed to get contacts by phone") from e

    async def get_contacts_by_email(
            self, email: str, limit: int = 10
    ) -> List[ContactItem]:
        """Get contacts by email address."""
        try:
            query = {"email": email}
            return await self.find_contacts(
                query,
                limit=limit,  # Already validated as int
            )
        except Exception as e:
            logger.error(f"Error getting contacts by email: {e}")
            from botspot.core.errors import ContactDataError
            raise ContactDataError("Failed to get contacts by email") from e


# ---------------------------------------------
# endregion Contact Manager Implementation
# ---------------------------------------------


# ---------------------------------------------
# region Command Handlers
# ---------------------------------------------

def setup_command_handlers(dp: Dispatcher, manager: ContactManager, settings: ContactManagerSettings):
    """Set up command handlers for contact management."""
    from botspot.commands_menu import Visibility

    router = Router(name="contact_manager")

    # Add command to add contact
    @commands_menu.add_command("add_contact", "Add a new contact", Visibility.PUBLIC)
    @router.message(Command("add_contact"))
    async def add_contact_cmd(message: Message):
        """Add a new contact."""
        # Extract contact info after the command
        if len(message.text.split()) <= 1:
            await message.reply(
                "Please provide contact information after the command. Example:\n"
                "/add_contact John Doe, phone: 555-1234, email: john@example.com"
            )
            return

        # Extract contact text (everything after the command)
        contact_text = message.text.split(maxsplit=1)[1]

        # Parse contact with LLM
        contact = await manager.parse_contact_with_llm(contact_text, message.from_user.id)

        if not contact:
            await message.reply("I couldn't parse the contact information. Please try again with more details.")
            return

        # Check if any required fields are missing
        missing_fields = []
        if not contact.phone and not contact.email and not contact.telegram:
            missing_fields.append("a way to contact (phone, email, or telegram)")

        # If missing fields, ask user to provide them
        if missing_fields:
            missing_info = ", ".join(missing_fields)
            await message.reply(
                f"I need {missing_info} for this contact. Please add this information and try again."
            )
            return

        # Add contact to database
        success = await manager.add_contact(contact, message.from_user.id)

        if success:
            await message.reply(
                f"✅ Contact added successfully!\n\n{contact.display_info}",
                parse_mode="Markdown"
            )
        else:
            await message.reply("❌ Failed to add contact. Please try again.")

    # Add command to find contact
    @commands_menu.add_command("find_contact", "Find contacts by name, phone, etc.", Visibility.PUBLIC)
    @router.message(Command("find_contact"))
    async def find_contact_cmd(message: Message):
        """Find contacts matching a search term."""
        if len(message.text.split()) <= 1:
            await message.reply(
                "Please provide a search term after the command. Example:\n"
                "/find_contact John"
            )
            return

        # Extract search text
        search_text = message.text.split(maxsplit=1)[1]

        # Search for contacts
        contacts = await manager.search_contacts(search_text, message.from_user.id)

        if not contacts:
            await message.reply(f"No contacts found matching '{search_text}'.")
            return

        # Format results
        if len(contacts) == 1:
            await message.reply(
                f"Found 1 contact:\n\n{contacts[0].display_info}",
                parse_mode="Markdown"
            )
        else:
            results = "\n\n".join([c.display_info for c in contacts[:5]])
            count_msg = f"Found {len(contacts)} contacts" + (", showing first 5:" if len(contacts) > 5 else ":")
            await message.reply(
                f"{count_msg}\n\n{results}",
                parse_mode="Markdown"
            )

    # Add command for random contact
    if settings.random_contact_enabled:
        @commands_menu.add_command("random_contact", "Get a random contact", Visibility.PUBLIC)
        @router.message(Command("random_contact"))
        async def random_contact_cmd(message: Message):
            """Get a random contact."""
            contact = await manager.get_random_contact(message.from_user.id)

            if not contact:
                await message.reply("You don't have any contacts saved yet.")
                return

            await message.reply(
                f"Random contact:\n\n{contact.display_info}",
                parse_mode="Markdown"
            )

    # Handle message parsing if enabled
    if settings.message_parser_enabled:
        @router.message()
        async def parse_contact_message(message: Message):
            """Parse potential contact information from regular messages."""
            # Skip commands
            if message.text and message.text.startswith('/'):
                return

            # Simple heuristic: Look for some indicators of contact info
            # This is intentionally simple as the LLM will do the heavy lifting
            if not message.text or not any(kw in message.text.lower() for kw in [
                'phone', 'email', 'telegram', '@', 'contact', 'reach', 'name'
            ]):
                return

            # Try to parse as contact
            contact = await manager.parse_contact_with_llm(message.text, message.from_user.id)

            # If we have a name and at least one contact method, offer to save
            if contact and contact.name and (contact.phone or contact.email or contact.telegram):
                await message.reply(
                    f"I detected contact information. Would you like to save this contact?\n\n"
                    f"{contact.display_info}\n\n"
                    f"Reply with /add_contact to confirm.",
                    parse_mode="Markdown"
                )

    # Include router in dispatcher
    dp.include_router(router)


# ---------------------------------------------
# endregion Command Handlers
# ---------------------------------------------


# ---------------------------------------------
# region Initialization and Setup
# ---------------------------------------------

def setup_dispatcher(dp: Dispatcher, **kwargs):
    """Setup contact manager component in the dispatcher."""
    settings = ContactManagerSettings(**kwargs)

    if not settings.enabled:
        logger.info("Contact Manager component is disabled")
        return dp

    # Make sure dependencies are available
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()

    if deps.contact_manager is None:
        logger.warning("Contact Manager component is not initialized")
        return dp

    logger.info("Setting up Contact Manager component")

    # Set up command handlers
    setup_command_handlers(dp, deps.contact_manager, settings)

    return dp


async def initialize(settings: ContactManagerSettings) -> ContactManager:
    """Initialize the Contact Manager component."""
    if not settings.enabled:
        logger.info("Contact Manager component is disabled")
        return ContactManager(settings)  # Return empty manager instead of None

    logger.info("Initializing Contact Manager component")
    manager = await ContactManager.create(settings)
    return manager


def get_contact_manager() -> ContactManager:
    """Get the Contact Manager from dependency manager."""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()

    if deps.contact_manager is None:
        raise RuntimeError("Contact Manager is not initialized")

    return deps.contact_manager


# ---------------------------------------------
# endregion Initialization and Setup
# ---------------------------------------------


# ---------------------------------------------
# region Utils
# ---------------------------------------------


async def add_contact(contact: ContactItem, owner_id: Optional[int] = None) -> bool:
    """Add a new contact to the database."""
    manager = get_contact_manager()
    return await manager.add_contact(contact, owner_id)


async def update_contact(contact_id: str, data: Dict[str, Any], owner_id: Optional[int] = None) -> bool:
    """Update an existing contact."""
    manager = get_contact_manager()
    return await manager.update_contact(contact_id, data, owner_id)


async def delete_contact(contact_id: str, owner_id: Optional[int] = None) -> bool:
    """Delete a contact by ID."""
    manager = get_contact_manager()
    return await manager.delete_contact(contact_id, owner_id)


async def get_contact_by_id(contact_id: str, owner_id: Optional[int] = None) -> Optional[ContactItem]:
    """Get a contact by ID."""
    manager = get_contact_manager()
    return await manager.get_contact_by_id(contact_id, owner_id)


async def find_contacts(query: Dict[str, Any], owner_id: Optional[int] = None, limit: int = 10) -> List[ContactItem]:
    """Find contacts matching the query."""
    manager = get_contact_manager()
    return await manager.find_contacts(query, limit, owner_id)


async def search_contacts(text: str, owner_id: Optional[int] = None, limit: int = 10) -> List[ContactItem]:
    """Search for contacts by name, email, etc."""
    manager = get_contact_manager()
    return await manager.search_contacts(text, limit, owner_id)


async def get_random_contact(owner_id: Optional[int] = None) -> Optional[ContactItem]:
    """Get a random contact."""
    manager = get_contact_manager()
    return await manager.get_random_contact(owner_id)


async def parse_contact_with_llm(text: str, owner_id: Optional[int] = None) -> Optional[ContactItem]:
    """Parse contact information from text using LLM."""
    manager = get_contact_manager()
    return await manager.parse_contact_with_llm(text, owner_id)


async def get_contacts_by_owner(owner_id: int, limit: int = 10) -> List[ContactItem]:
    """Get all contacts owned by a specific user."""
    manager = get_contact_manager()
    return await manager.get_contacts_by_owner(owner_id, limit)


async def get_contacts_by_telegram(telegram: str, limit: int = 10) -> List[ContactItem]:
    """Get contacts by Telegram username."""
    manager = get_contact_manager()
    return await manager.get_contacts_by_telegram(telegram, limit)


async def get_contacts_by_phone(phone: str, limit: int = 10) -> List[ContactItem]:
    """Get contacts by phone number."""
    manager = get_contact_manager()
    return await manager.get_contacts_by_phone(phone, limit)


async def get_contacts_by_email(email: str, limit: int = 10) -> List[ContactItem]:
    """Get contacts by email address."""
    manager = get_contact_manager()
    return await manager.get_contacts_by_email(email, limit)

# ---------------------------------------------
# endregion Utils
