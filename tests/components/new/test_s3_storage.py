from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from botspot.components.new.s3_storage import S3StorageProvider, S3StorageSettings, initialize


@pytest.fixture
def mock_aioboto3():
    """Mock aioboto3 for testing."""
    with patch("aioboto3.Session") as mock_session:
        mock_client = AsyncMock()
        mock_session.return_value.client.return_value.__aenter__.return_value = mock_client
        yield mock_client


@pytest.fixture
def s3_settings():
    """Return S3StorageSettings instance for testing."""
    return S3StorageSettings(
        enabled=True,
        bucket_name="test-bucket",
        region="us-east-1",
        access_key_id="test-key",
        secret_access_key="test-secret",
        skip_import_check=True,
    )


@pytest.fixture
def s3_provider(s3_settings, mock_aioboto3):
    """Return initialized S3StorageProvider instance."""
    return S3StorageProvider(s3_settings)


async def test_upload_file(s3_provider, mock_aioboto3):
    """Test file upload functionality."""
    content = b"test content"
    key = "test.txt"

    await s3_provider.upload_file(key, content)

    mock_aioboto3.put_object.assert_called_once_with(Bucket="test-bucket", Key=key, Body=content)


async def test_download_file(s3_provider, mock_aioboto3):
    """Test file download functionality."""
    content = b"test content"
    key = "test.txt"

    mock_aioboto3.get_object.return_value = {
        "Body": AsyncMock(read=AsyncMock(return_value=content))
    }

    result = await s3_provider.download_file(key)
    assert result == content

    mock_aioboto3.get_object.assert_called_once_with(Bucket="test-bucket", Key=key)


async def test_delete_file(s3_provider, mock_aioboto3):
    """Test file deletion functionality."""
    key = "test.txt"

    await s3_provider.delete_file(key)

    mock_aioboto3.delete_object.assert_called_once_with(Bucket="test-bucket", Key=key)


async def test_list_files(s3_provider, mock_aioboto3):
    """Test file listing functionality."""
    prefix = "test/"
    files = ["test/file1.txt", "test/file2.txt"]

    mock_paginator = AsyncMock()
    mock_paginator.paginate.return_value = [{"Contents": [{"Key": key} for key in files]}]
    mock_aioboto3.get_paginator.return_value = mock_paginator

    result = []
    async for file in s3_provider.list_files(prefix):
        result.append(file)

    assert result == files
    mock_aioboto3.get_paginator.assert_called_once_with("list_objects_v2")


async def test_upload_file_stream(s3_provider, mock_aioboto3):
    """Test streaming file upload functionality."""
    key = "test.txt"
    stream = MagicMock()

    await s3_provider.upload_file_stream(key, stream)

    mock_aioboto3.upload_fileobj.assert_called_once_with(stream, "test-bucket", key)


async def test_download_file_stream(s3_provider, mock_aioboto3):
    """Test streaming file download functionality."""
    key = "test.txt"
    chunks = [b"chunk1", b"chunk2"]

    mock_aioboto3.get_object.return_value = {
        "Body": AsyncMock(iter_chunks=AsyncMock(return_value=chunks))
    }

    result = []
    async for chunk in s3_provider.download_file_stream(key):
        result.append(chunk)

    assert result == chunks
    mock_aioboto3.get_object.assert_called_once_with(Bucket="test-bucket", Key=key)


def test_initialize_disabled():
    """Test initialization when component is disabled."""
    settings = S3StorageSettings(enabled=False)
    provider = initialize(settings)
    assert provider is None


def test_initialize_success(s3_settings, mock_aioboto3):
    """Test successful initialization."""
    provider = initialize(s3_settings)
    assert isinstance(provider, S3StorageProvider)
    assert provider.settings == s3_settings
