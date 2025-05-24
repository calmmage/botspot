import argparse
import logging
import os
import tempfile

import pyrogram
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Argument parsing
parser = argparse.ArgumentParser(description="Download a file from Telegram using Pyrogram.")
parser.add_argument(
    "--chat-id",
    required=True,
    help="ID of the chat from which the file should be downloaded.",
)
parser.add_argument(
    "--message-id",
    required=True,
    type=int,
    help="ID of the message containing the file.",
)
parser.add_argument(
    "--target-path",
    default=None,
    help="Path to save the downloaded file. Generates a temporary path if not provided.",
)
parser.add_argument("--token", default=os.getenv("TELEGRAM_BOT_TOKEN"))
parser.add_argument("--api-id", default=os.getenv("TELEGRAM_BOT_API_ID"))
parser.add_argument("--api-hash", default=os.getenv("TELEGRAM_BOT_API_HASH"))

args = parser.parse_args()

# Setup pyrogram client
app = pyrogram.Client(
    "telegram_downloader",
    api_id=args.api_id,
    api_hash=args.api_hash,
    bot_token=args.token,
)

target_path = args.target_path
# If target_path is not provided, generate a temp path
if not target_path:
    _, target_path = tempfile.mkstemp()


async def main():
    async with app:
        message = await app.get_messages(args.chat_id, message_ids=args.message_id)
        result = await message.download(file_name=target_path)
    print(target_path)


if __name__ == "__main__":
    app.run(main())
