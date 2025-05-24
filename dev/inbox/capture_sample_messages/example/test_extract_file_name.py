import pickle
from pathlib import Path
import pytest

# from aiogram.types import Message
from pyrogram.types import Message as PyrogramMessage
# from dev.pyrogram_file_loader import extract_file_name_from_pyrogram_message

SAMPLE_DIR = Path(__file__).parent / "sample_messages"


def extract_file_name_from_pyrogram_message(msg: PyrogramMessage) -> str:
    # Try document, audio, video (these have file_name)
    for attr in ("document", "audio", "video"):
        media = getattr(msg, attr, None)
        if media and getattr(media, "file_name", None):
            return media.file_name
    # Voice, video_note, photo: generate default name
    if msg.voice:
        return f"{msg.voice.file_id}.ogg"
    if msg.video_note:
        return f"{msg.video_note.file_id}.mp4"
    if msg.photo:
        # Use the largest photo size
        photo = msg.photo[-1] if isinstance(msg.photo, list) else msg.photo
        return f"{photo.file_id}.jpg"
    # Fallback
    return "file.bin"


@pytest.mark.parametrize(
    "pkl_file, target_file_name",
    [
        (SAMPLE_DIR / "sample_audio_attached.pkl", "GMT20250522-065206_Recording.m4a"),
        (SAMPLE_DIR / "sample_video_attached.pkl", "IMG_3025.MOV"),
        (
            SAMPLE_DIR / "sample_voice_attached.pkl",
            "AwACAgIAAxkBAAIdgmgwqXZ4iqbDK_S8F1ZN0F9p_7IeAAJrdgACnaKBSbxoexmGcmvTHgQ.ogg",
        ),
        (
            SAMPLE_DIR / "sample_video_note_attached.pkl",
            "DQACAgIAAxkBAAIdfmgwqRL9zE9xD9L7daUrk5ROO2gwAAI3dwAChhuBSazsF4Dv8MUaHgQ.mp4",
        ),
        (
            SAMPLE_DIR / "sample_photo_attached.pkl",
            "AgACAgIAAxkBAAIdgGgwqWBUD5NHH2Tl5EWdEg1I9f7XAALLBTIbnaKBSZB_Hq-V73AKAAgBAAMCAAN5AAceBA.jpg",
        ),
        (SAMPLE_DIR / "sample_document_attached.pkl", "receipt_17.05.2025.pdf"),
    ],
)
def test_extract_file_name(pkl_file, target_file_name):
    msg = pickle.load(open(pkl_file, "rb"))
    file_name = extract_file_name_from_pyrogram_message(msg)
    print(f"{pkl_file.name}: {file_name}")
    assert file_name == target_file_name
    assert isinstance(file_name, str) and len(file_name) > 0
