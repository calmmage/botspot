async def download_large_file(chat_id, message_id, target_path=None):
    # todo: troubleshoot chat_id. Only username works for now.
    _check_pyrogram_tokens()

    script_path = download_large_file_script_path

    # todo: update, rework config, make it per-user
    # Construct command to run the download script
    cmd = [
        "python",
        str(script_path),
        "--chat-id",
        str(chat_id),
        "--message-id",
        str(message_id),
        "--token",
        config.token.get_secret_value(),
        "--api-id",
        config.api_id.get_secret_value(),
        "--api-hash",
        config.api_hash.get_secret_value(),
    ]

    if target_path:
        cmd.extend(["--target-path", target_path])
    else:
        _, file_path = mkstemp(dir=downloads_dir)
        cmd.extend(["--target-path", file_path])
    logger.debug(f"Running command: {' '.join(cmd)}")
    # Run the command in a separate thread and await its result
    # todo: check if this actually still works
    result = await asyncio.to_thread(subprocess.run, cmd, capture_output=True)
    err = result.stderr.strip().decode("utf-8")
    if "ERROR" in err:
        raise Exception(err)
    file_path = result.stdout.strip().decode("utf-8")
    logger.debug(f"{result.stdout=}\n\n{result.stderr=}")
    if target_path is None:
        file_data = BytesIO(open(file_path, "rb").read())
        os.unlink(file_path)
        return file_data
    return file_path
