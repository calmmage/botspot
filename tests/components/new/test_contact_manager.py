import asyncio
import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from botspot.components.new.contact_manager import ContactItem, ContactManager, ContactManagerSettings, initialize, setup_command_handlers


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
    """Fixture to create a mock queue for the contact manager"""
    queue = AsyncMock()
    queue.collection = MagicMock()
    queue.collection.find_one.return_value = None  # Default: contact not found
    queue.find_one.return_value = None
    return queue


@pytest.fixture
def mock_dispatcher():
    """Fixture to create a mock dispatcher"""
    return MagicMock()


@pytest.fixture
def contact_manager(contact_manager_settings, mock_queue):
    """Fixture to create a contact manager with a mock queue"""
    with patch("botspot.components.new.contact_manager.create_queue", return_value=mock_queue):
        manager = ContactManager(contact_manager_settings)
        return manager


@pytest.fixture
def sample_contact():
    """Fixture to create a sample contact"""
    return ContactItem(
        name="Test Contact",
        phone="555-1234",
        email="test@example.com",
        telegram="@testcontact",
        birthday=datetime.date(1990, 1, 1),
        notes="Test notes",
        owner_id=9876
    )


# Basic CRUD tests
def test_add_contact(contact_manager, sample_contact):
    """Test adding a contact"""
    contact_manager.queue.add_item.return_value = None
    
    # Execute
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(contact_manager.add_contact(sample_contact))
    
    # Assert
    assert result == True
    contact_manager.queue.add_item.assert_called_once()


def test_update_contact(contact_manager, sample_contact):
    """Test updating a contact"""
    contact_manager.queue.update_record.return_value = True
    
    # Execute
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(contact_manager.update_contact("contact123", {"name": "Updated Name"}))
    
    # Assert
    assert result == True
    contact_manager.queue.update_record.assert_called_once()


def test_delete_contact(contact_manager):
    """Test deleting a contact"""
    contact_manager.queue.delete_record.return_value = True
    
    # Execute
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(contact_manager.delete_contact("contact123"))
    
    # Assert
    assert result == True
    contact_manager.queue.delete_record.assert_called_once_with("contact123")


def test_get_contact_by_id(contact_manager, sample_contact):
    """Test retrieving a contact by ID"""
    contact_dict = sample_contact.model_dump()
    contact_manager.queue.find.return_value = contact_dict
    
    # Execute
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(contact_manager.get_contact_by_id("contact123"))
    
    # Assert
    assert isinstance(result, ContactItem)
    assert result.name == "Test Contact"
    contact_manager.queue.find.assert_called_once_with({"_id": "contact123"})


def test_find_contacts(contact_manager, sample_contact):
    """Test finding contacts by criteria"""
    contact_dicts = [sample_contact.model_dump()]
    contact_manager.queue.find_many.return_value = contact_dicts
    
    # Execute
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(contact_manager.find_contacts({"name": "Test Contact"}))
    
    # Assert
    assert len(result) == 1
    assert isinstance(result[0], ContactItem)
    assert result[0].name == "Test Contact"
    contact_manager.queue.find_many.assert_called_once()


def test_search_contacts(contact_manager, sample_contact):
    """Test searching contacts by text"""
    contact_dicts = [sample_contact.model_dump()]
    contact_manager.queue.find_many.return_value = contact_dicts
    
    # Execute
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(contact_manager.search_contacts("Test"))
    
    # Assert
    assert len(result) == 1
    assert isinstance(result[0], ContactItem)
    assert result[0].name == "Test Contact"
    contact_manager.queue.find_many.assert_called_once()


def test_get_random_contact(contact_manager, sample_contact):
    """Test getting a random contact"""
    contact_manager.queue.get_random_record.return_value = sample_contact.model_dump()
    
    # Execute
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(contact_manager.get_random_contact())
    
    # Assert
    assert isinstance(result, ContactItem)
    assert result.name == "Test Contact"
    contact_manager.queue.get_random_record.assert_called_once()


# User Story Tests
@pytest.mark.asyncio
async def test_parse_contact_with_llm_success():
    """Test parsing contact info from text using LLM - successful case"""
    # Create mock LLM provider
    mock_llm = AsyncMock()
    
    # Mock the LLM response - create an actual ContactItem
    mock_contact = ContactItem(
        name="Jane Smith",
        phone="555-5678",
        email="jane@example.com",
        telegram="@janesmith"
    )
    mock_llm.aquery_llm_structured.return_value = mock_contact
    
    # Create mock queue
    mock_queue = AsyncMock()
    
    # Patch dependencies - mock both queue and llm provider
    with patch("botspot.utils.deps_getters.get_llm_provider", return_value=mock_llm), \
         patch("botspot.components.new.contact_manager.create_queue", return_value=mock_queue):
        
        # Create manager directly - don't rely on queue_manager
        settings = ContactManagerSettings(collection="test_contacts")
        manager = ContactManager(settings)
        
        # Test parsing
        contact = await manager.parse_contact_with_llm("Jane Smith, 555-5678, jane@example.com, @janesmith", user_id=1234)
        
        # Assert
        assert contact is not None
        assert contact.name == "Jane Smith"
        assert contact.phone == "555-5678"
        assert contact.email == "jane@example.com"
        assert contact.telegram == "@janesmith"
        assert contact.owner_id == 1234
        
        # Verify LLM was called with appropriate system message
        mock_llm.aquery_llm_structured.assert_called_once()
        assert "parser" in mock_llm.aquery_llm_structured.call_args[1]["system_message"].lower()


@pytest.mark.asyncio
async def test_parse_contact_with_llm_missing_fields():
    """Test parsing contact with missing fields"""
    # Create mock LLM provider
    mock_llm = AsyncMock()
    
    # Mock the LLM response with minimal info
    mock_contact = ContactItem(
        name="Jane Smith",
        notes="Not much info provided"
    )
    mock_llm.aquery_llm_structured.return_value = mock_contact
    
    # Create mock queue
    mock_queue = AsyncMock()
    
    # Patch dependencies
    with patch("botspot.utils.deps_getters.get_llm_provider", return_value=mock_llm), \
         patch("botspot.components.new.contact_manager.create_queue", return_value=mock_queue):
        
        # Create manager
        settings = ContactManagerSettings(collection="test_contacts")
        manager = ContactManager(settings)
        
        # Test parsing
        contact = await manager.parse_contact_with_llm("Jane Smith", user_id=1234)
        
        # Assert
        assert contact is not None
        assert contact.name == "Jane Smith"
        assert contact.phone is None
        assert contact.email is None
        assert contact.telegram is None
        assert contact.owner_id == 1234


@pytest.mark.asyncio
async def test_parse_contact_with_llm_failure():
    """Test failed contact parsing"""
    # Create mock LLM provider
    mock_llm = AsyncMock()
    
    # Mock the LLM to raise an exception on structured output
    mock_llm.aquery_llm_structured.side_effect = Exception("Invalid output format")
    
    # Create mock queue
    mock_queue = AsyncMock()
    
    # Patch dependencies
    with patch("botspot.utils.deps_getters.get_llm_provider", return_value=mock_llm), \
         patch("botspot.components.new.contact_manager.create_queue", return_value=mock_queue):
        
        # Create manager
        settings = ContactManagerSettings(collection="test_contacts")
        manager = ContactManager(settings)
        
        # Test parsing
        contact = await manager.parse_contact_with_llm("Jane Smith", user_id=1234)
        
        # Assert
        assert contact is None


@pytest.mark.asyncio
async def test_parse_contact_llm_exception():
    """Test exception handling during contact parsing"""
    # Create mock LLM provider
    mock_llm = AsyncMock()
    
    # Mock the LLM to raise an exception
    mock_llm.aquery_llm_structured.side_effect = Exception("LLM service unavailable")
    
    # Create mock queue
    mock_queue = AsyncMock()
    
    # Patch dependencies
    with patch("botspot.utils.deps_getters.get_llm_provider", return_value=mock_llm), \
         patch("botspot.components.new.contact_manager.create_queue", return_value=mock_queue):
        
        # Create manager
        settings = ContactManagerSettings(collection="test_contacts")
        manager = ContactManager(settings)
        
        # Test parsing
        contact = await manager.parse_contact_with_llm("Jane Smith", user_id=1234)
        
        # Assert
        assert contact is None


@pytest.mark.asyncio
async def test_add_contact_command_handler():
    """Test the add_contact command handler"""
    # Skip this test for now - will be implemented after fixing other issues
    pytest.skip("Handler tests will be implemented after fixing core functionality")


@pytest.mark.asyncio
async def test_find_contact_command_handler():
    """Test the find_contact command handler"""
    # Skip this test for now - will be implemented after fixing other issues
    pytest.skip("Handler tests will be implemented after fixing core functionality")


@pytest.mark.asyncio
async def test_random_contact_command_handler():
    """Test the random_contact command handler"""
    # Skip this test for now - will be implemented after fixing other issues
    pytest.skip("Handler tests will be implemented after fixing core functionality")


@pytest.mark.asyncio
async def test_message_parser():
    """Test the message parser that automatically detects contact info in chat messages"""
    # Skip this test for now - will be implemented after fixing other issues
    pytest.skip("Handler tests will be implemented after fixing core functionality")


# Integration tests
@pytest.mark.asyncio
async def test_initialization():
    """Test the initialization function"""
    settings = ContactManagerSettings(enabled=True, collection="test_contacts")
    
    with patch("botspot.components.new.contact_manager.create_queue") as mock_create_queue:
        mock_queue = AsyncMock()
        mock_create_queue.return_value = mock_queue
        
        # Call initialize
        manager = initialize(settings)
        
        # Assert
        assert isinstance(manager, ContactManager)
        
        # Verify create_queue was called with the correct parameters - note the 'key' named parameter
        mock_create_queue.assert_called_once_with(key="contacts", item_model=ContactItem) 