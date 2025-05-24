import pickle
from pathlib import Path
from pyrogram import Client, filters
from dotenv import load_dotenv
import os

load_dotenv()
API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SAMPLE_DIR = Path(__file__).parent / "sample_messages"
SAMPLE_DIR.mkdir(exist_ok=True)

app = Client("capture_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

MEDIA_TYPES = [
    ("audio", filters.audio),
    ("video", filters.video),
    ("document", filters.document),
    ("voice", filters.voice),
    ("video_note", filters.video_note),
    ("photo", filters.photo),
]

for type_name, media_filter in MEDIA_TYPES:

    @app.on_message(media_filter)
    async def handler(client, message, type_name=type_name):
        file_path = SAMPLE_DIR / f"sample_{type_name}_attached.pkl"
        with open(file_path, "wb") as f:
            pickle.dump(message, f)
        await message.reply_text(
            f"Captured {type_name} and saved to {file_path.name}. Type: {type(message)}"
        )


if __name__ == "__main__":
    app.run()
