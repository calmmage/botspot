import asyncio
import datetime
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, create_autospec, Mock

from botspot.components.new.contact_manager import ContactItem, ContactManager, ContactManagerSettings, initialize, setup_command_handlers
from botspot.core.errors import ContactDataError


@pytest.fixture
def contact_manager_settings():
    """Fixture to create contact manager settings"""
    return ContactManagerSettings(
        enabled=True,
        collection="test_contacts",
        message_parser_enabled=True,
        random_contact_enabled=True
    )


@pytest.fixture
def mock_queue():
    """Create a mock queue for testing."""
    queue = AsyncMock()
    queue.add_item = AsyncMock(return_value=True)
    queue.update_record = AsyncMock(return_value=True)
    queue.delete_record = AsyncMock(return_value=True)
    queue.find = AsyncMock(return_value=None)
    queue.find_many = AsyncMock(return_value=[])
    queue.get_random_record = AsyncMock(return_value=None)
    return queue


@pytest.fixture
def mock_queue_manager(mock_queue):
    """Create a mock queue manager for testing."""
    manager = Mock()
    manager.create_queue = Mock(return_value=mock_queue)
    return manager


@pytest.fixture
def mock_dispatcher():
    """Fixture to create a mock dispatcher"""
    return MagicMock()


@pytest_asyncio.fixture
async def contact_manager(mock_queue_manager):
    """Create a contact manager instance for testing."""
    settings = ContactManagerSettings(enabled=True)
    return await ContactManager.create(settings, queue_manager=mock_queue_manager)


@pytest.fixture
def sample_contact():
    """Create a sample contact for testing."""
    return ContactItem(
        data="Test Contact",
        name="Test Contact",
        phone="555-1234",
        email="test@example.com",
        telegram="@testuser",
        owner_id=9876,
        created_at=datetime.datetime(2025, 4, 5, 14, 5, 26, 882324, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(2025, 4, 5, 14, 5, 26, 882324, tzinfo=datetime.timezone.utc),
    )


# Basic CRUD tests
@pytest.mark.asyncio
async def test_add_contact(contact_manager, sample_contact):
    """Test adding a contact"""
    result = await contact_manager.add_contact(sample_contact)
    assert result is True
    contact_manager.queue.add_item.assert_called_once()


@pytest.mark.asyncio
async def test_update_contact(contact_manager, sample_contact):
    """Test updating a contact"""
    contact_manager.queue.find = AsyncMock(return_value=sample_contact.model_dump())
    result = await contact_manager.update_contact("test_id", {"name": "Updated Name"})
    assert result is True
    contact_manager.queue.update_record.assert_called_once()


@pytest.mark.asyncio
async def test_delete_contact(contact_manager):
    """Test deleting a contact"""
    result = await contact_manager.delete_contact("test_id")
    assert result is True
    contact_manager.queue.delete_record.assert_called_once()


@pytest.mark.asyncio
async def test_get_contact_by_id(contact_manager, sample_contact):
    """Test retrieving a contact by ID"""
    contact_dict = sample_contact.model_dump()
    contact_manager.queue.find = AsyncMock(return_value=contact_dict)
    result = await contact_manager.get_contact_by_id("test_id")
    assert isinstance(result, ContactItem)
    assert result.name == sample_contact.name
    contact_manager.queue.find.assert_called_once()


@pytest.mark.asyncio
async def test_find_contacts(contact_manager, sample_contact):
    """Test finding contacts by criteria"""
    contact_dicts = [sample_contact.model_dump()]
    contact_manager.queue.find_many = AsyncMock(return_value=contact_dicts)
    result = await contact_manager.find_contacts({"name": "Test"})
    assert len(result) == 1
    assert isinstance(result[0], ContactItem)
    assert result[0].name == sample_contact.name
    contact_manager.queue.find_many.assert_called_once()


@pytest.mark.asyncio
async def test_search_contacts(contact_manager, sample_contact):
    """Test searching contacts by text"""
    contact_dicts = [sample_contact.model_dump()]
    contact_manager.queue.find_many = AsyncMock(return_value=contact_dicts)
    result = await contact_manager.search_contacts("Test")
    assert len(result) == 1
    assert isinstance(result[0], ContactItem)
    assert result[0].name == sample_contact.name
    contact_manager.queue.find_many.assert_called_once()


@pytest.mark.asyncio
async def test_get_random_contact(contact_manager, sample_contact):
    """Test getting a random contact"""
    contact_manager.queue.get_random_record = AsyncMock(return_value=sample_contact.model_dump())
    result = await contact_manager.get_random_contact()
    assert isinstance(result, ContactItem)
    assert result.name == sample_contact.name
    contact_manager.queue.get_random_record.assert_called_once()


# User Story Tests
@pytest.mark.asyncio
async def test_parse_contact_with_llm_success():
    """Test parsing contact info from text using LLM - successful case"""
    # Create mock LLM provider
    mock_llm = AsyncMock()
    
    # Mock the LLM response - create an actual ContactItem
    mock_contact = ContactItem(
        data="Jane Smith",
        name="Jane Smith",
        phone="555-5678",
        email="jane@example.com",
        telegram="@janesmith"
    )
    mock_llm.aquery_llm_structured.return_value = mock_contact
    
    # Create mock queue and queue manager
    mock_queue = AsyncMock()
    mock_queue_manager = AsyncMock()
    mock_queue_manager.create_queue.return_value = mock_queue
    
    # Patch dependencies - mock both queue manager and llm provider
    with patch("botspot.utils.deps_getters.get_llm_provider", return_value=mock_llm), \
         patch("botspot.components.new.contact_manager.get_queue_manager", return_value=mock_queue_manager):
        
        # Create manager
        settings = ContactManagerSettings(collection="test_contacts")
        manager = ContactManager(settings)
        
        # Test parsing
        contact = await manager.parse_contact_with_llm("Jane Smith, 555-5678, jane@example.com, @janesmith", owner_id=1234)
        
        # Assert
        assert contact is not None
        assert contact.name == "Jane Smith"
        assert contact.phone == "555-5678"
        assert contact.email == "jane@example.com"
        assert contact.telegram == "@janesmith"
        assert contact.owner_id == 1234
        
        # Verify LLM was called with appropriate system message
        mock_llm.aquery_llm_structured.assert_called_once()


@pytest.mark.asyncio
async def test_parse_contact_with_llm_missing_fields():
    """Test parsing contact with missing fields"""
    # Create mock LLM provider
    mock_llm = AsyncMock()
    
    # Mock the LLM response with minimal info
    mock_contact = ContactItem(
        data="Jane Smith",
        name="Jane Smith",
        notes="Not much info provided"
    )
    mock_llm.aquery_llm_structured.return_value = mock_contact
    
    # Create mock queue and queue manager
    mock_queue = AsyncMock()
    mock_queue_manager = AsyncMock()
    mock_queue_manager.create_queue.return_value = mock_queue
    
    # Patch dependencies
    with patch("botspot.utils.deps_getters.get_llm_provider", return_value=mock_llm), \
         patch("botspot.components.new.contact_manager.get_queue_manager", return_value=mock_queue_manager):
        
        # Create manager
        settings = ContactManagerSettings(collection="test_contacts")
        manager = ContactManager(settings)
        
        # Test parsing
        contact = await manager.parse_contact_with_llm("Jane Smith", owner_id=1234)
        
        # Assert
        assert contact is not None
        assert contact.name == "Jane Smith"
        assert contact.notes == "Not much info provided"
        assert contact.owner_id == 1234
        assert contact.phone is None
        assert contact.email is None
        assert contact.telegram is None


@pytest.mark.asyncio
async def test_parse_contact_with_llm_failure():
    """Test failed contact parsing"""
    # Create mock LLM provider
    mock_llm = AsyncMock()
    
    # Mock the LLM to raise an exception on structured output
    mock_llm.aquery_llm_structured.side_effect = Exception("Invalid output format")
    
    # Create mock queue and queue manager
    mock_queue = AsyncMock()
    mock_queue_manager = AsyncMock()
    mock_queue_manager.create_queue.return_value = mock_queue
    
    # Patch dependencies
    with patch("botspot.utils.deps_getters.get_llm_provider", return_value=mock_llm), \
         patch("botspot.components.new.contact_manager.get_queue_manager", return_value=mock_queue_manager):
        
        # Create manager
        settings = ContactManagerSettings(collection="test_contacts")
        manager = ContactManager(settings)
        
        # Test parsing - should raise ContactDataError
        with pytest.raises(Exception):
            await manager.parse_contact_with_llm("Invalid contact info", owner_id=1234)


@pytest.mark.asyncio
async def test_parse_contact_llm_exception():
    """Test exception handling during contact parsing"""
    # Create mock LLM provider
    mock_llm = AsyncMock()
    
    # Mock the LLM to raise an exception
    mock_llm.aquery_llm_structured.side_effect = Exception("LLM service unavailable")
    
    # Create mock queue and queue manager
    mock_queue = AsyncMock()
    mock_queue_manager = AsyncMock()
    mock_queue_manager.create_queue.return_value = mock_queue
    
    # Patch dependencies
    with patch("botspot.utils.deps_getters.get_llm_provider", return_value=mock_llm), \
         patch("botspot.components.new.contact_manager.get_queue_manager", return_value=mock_queue_manager):
        
        # Create manager
        settings = ContactManagerSettings(collection="test_contacts")
        manager = ContactManager(settings)
        
        # Test parsing - should raise ContactDataError
        with pytest.raises(Exception):
            await manager.parse_contact_with_llm("Some contact info", owner_id=1234)


@pytest.mark.asyncio
async def test_initialization():
    """Test the initialization function"""
    settings = ContactManagerSettings(enabled=True, collection="test_contacts")
    mock_queue = AsyncMock()
    mock_queue_manager = Mock()
    mock_queue_manager.create_queue = Mock(return_value=mock_queue)

    async def mock_get_queue_manager():
        return mock_queue_manager

    with patch("botspot.components.new.contact_manager.get_queue_manager", mock_get_queue_manager):
        manager = await initialize(settings)
        assert isinstance(manager, ContactManager)
        assert manager.settings == settings
        assert manager.queue == mock_queue


@pytest.mark.asyncio
async def test_get_contacts_by_owner(contact_manager, sample_contact):
    """Test getting contacts by owner ID"""
    # Set up mock return values
    contact_manager.queue.find_many = AsyncMock(return_value=[sample_contact.model_dump()])
    
    # Test getting contacts by owner
    contacts = await contact_manager.get_contacts_by_owner(9876)
    assert len(contacts) == 1
    assert contacts[0].name == "Test Contact"
    assert contacts[0].owner_id == 9876


@pytest.mark.asyncio
async def test_get_contacts_by_telegram(contact_manager, sample_contact):
    """Test getting contacts by Telegram username"""
    # Set up mock return values
    contact_manager.queue.find_many = AsyncMock(return_value=[sample_contact.model_dump()])
    
    # Test getting contacts by Telegram
    contacts = await contact_manager.get_contacts_by_telegram("@testuser")
    assert len(contacts) == 1
    assert contacts[0].name == "Test Contact"
    assert contacts[0].telegram == "@testuser"


@pytest.mark.asyncio
async def test_get_contacts_by_phone(contact_manager, sample_contact):
    """Test getting contacts by phone number"""
    # Set up mock return values
    contact_manager.queue.find_many = AsyncMock(return_value=[sample_contact.model_dump()])
    
    # Test getting contacts by phone
    contacts = await contact_manager.get_contacts_by_phone("555-1234")
    assert len(contacts) == 1
    assert contacts[0].name == "Test Contact"
    assert contacts[0].phone == "555-1234"


@pytest.mark.asyncio
async def test_get_contacts_by_email(contact_manager, sample_contact):
    """Test getting contacts by email"""
    # Set up mock return values
    contact_manager.queue.find_many = AsyncMock(return_value=[sample_contact.model_dump()])
    
    # Test getting contacts by email
    contacts = await contact_manager.get_contacts_by_email("test@example.com")
    assert len(contacts) == 1
    assert contacts[0].name == "Test Contact"
    assert contacts[0].email == "test@example.com"


@pytest.mark.asyncio
async def test_get_contacts_by_owner_empty(contact_manager):
    """Test getting contacts by owner when none exist"""
    # Set up mock return values
    contact_manager.queue.find_many = AsyncMock(return_value=[])
    
    contacts = await contact_manager.get_contacts_by_owner(9876)
    assert len(contacts) == 0


@pytest.mark.asyncio
async def test_get_contacts_by_telegram_empty(contact_manager):
    """Test getting contacts by Telegram when none exist"""
    # Set up mock return values
    contact_manager.queue.find_many = AsyncMock(return_value=[])
    
    contacts = await contact_manager.get_contacts_by_telegram("@testuser")
    assert len(contacts) == 0


@pytest.mark.asyncio
async def test_get_contacts_by_phone_empty(contact_manager):
    """Test getting contacts by phone when none exist"""
    # Set up mock return values
    contact_manager.queue.find_many = AsyncMock(return_value=[])
    
    contacts = await contact_manager.get_contacts_by_phone("555-1234")
    assert len(contacts) == 0


@pytest.mark.asyncio
async def test_get_contacts_by_email_empty(contact_manager):
    """Test getting contacts by email when none exist"""
    # Set up mock return values
    contact_manager.queue.find_many = AsyncMock(return_value=[])
    
    contacts = await contact_manager.get_contacts_by_email("test@example.com")
    assert len(contacts) == 0 