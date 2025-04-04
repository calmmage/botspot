import json
import random
from pathlib import Path

easter_eggs_file_path = Path(__file__).parent / "easter_eggs.json"
easter_eggs = json.load(open(easter_eggs_file_path, encoding="utf-8"))
pongs_file_path = Path(__file__).parent / "pongs.json"
pongs = json.load(open(pongs_file_path, encoding="utf-8"))


def get_easter_egg() -> str:
    return random.choice(easter_eggs)


def get_pong() -> str:
    return random.choice(pongs)


if __name__ == "__main__":
    print(get_easter_egg())

__all__ = [
    "get_easter_egg",
    "get_pong",
    "easter_eggs",
    "pongs",
]
