from calmlib.utils.audio_utils import split_and_transcribe_audio
from loguru import logger

from botspot.core.dependency_manager import get_dependency_manager
from dev.draft.large_file_download.large_file_donwload import download_large_file


async def download_file(message: types.Message, file_desc, file_path=None):
    # todo: get bot from deps
    deps = get_dependency_manager()
    if file_desc.file_size < 20 * 1024 * 1024:
        return await deps.bot.download(file_desc.file_id, destination=file_path)
    else:
        return await download_large_file(message.chat.username, message.message_id, target_path=file_path)


async def _process_voice_message(message, parallel=None):
    # extract and parse message with whisper api
    # todo: use smart filters for voice messages?
    if message.audio:
        logger.debug(f"Detected audio message")
        file_desc = message.audio
    elif message.voice:
        logger.debug(f"Detected voice message")
        file_desc = message.voice
    else:
        raise ValueError("No audio file detected")

    file = await download_file(message, file_desc)
    return await split_and_transcribe_audio(file, parallel=parallel)
