import random
from pathlib import Path

import yaml

file_path = Path(__file__).parent / "easter_eggs.yaml"

easter_eggs = yaml.safe_load(open(file_path, encoding="utf-8"))["items"]


def get_easter_egg() -> str:
    return random.choice(easter_eggs)


if __name__ == "__main__":
    print(get_easter_egg())
