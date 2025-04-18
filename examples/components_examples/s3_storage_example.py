from botspot.utils.deps_getters import get_s3_storage


async def example():
    """Example usage of S3 storage component."""
    s3 = get_s3_storage()
    if s3 is None:
        print("S3 storage is not enabled")
        return

    # Upload a file
    await s3.upload_file("test.txt", b"Hello World")

    # Download a file
    content = await s3.download_file("test.txt")
    print(f"Downloaded content: {content.decode()}")

    # List files
    print("Files in bucket:")
    async for file in s3.list_files():
        print(f"- {file}")

    # Delete a file
    await s3.delete_file("test.txt")

    # Stream upload
    with open("large_file.txt", "rb") as f:
        await s3.upload_file_stream("large_file.txt", f)

    # Stream download
    async for chunk in s3.download_file_stream("large_file.txt"):
        print(f"Received chunk: {len(chunk)} bytes")
