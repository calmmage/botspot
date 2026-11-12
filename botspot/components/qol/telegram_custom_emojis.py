"""Outgoing custom Telegram emoji.

Off unless enabled. Outgoing message text and captions then use
`<tg-emoji emoji-id="...">fallback</tg-emoji>` (HTML) or a `custom_emoji`
entity (plain text). A leading emoji on a button becomes
`icon_custom_emoji_id`. Ids come from Petr's telegram-emoji catalog.

`pack` is `random`, one catalog pack name, or a comma-separated list.
`random` and a list pick one pack per message (`random_scope=message`)
or once per process (`random_scope=process`). Glyphs missing from that
pack use another catalog pack when `allow_other_packs` is on.

Env: `BOTSPOT_TELEGRAM_CUSTOM_EMOJIS_ENABLED`, `_PACK`, `_RANDOM_SCOPE`,
`_ALLOW_OTHER_PACKS`.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.client.default import Default
from aiogram.types import MessageEntity
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

logger = get_logger()

CATALOG_FILE = Path(__file__).with_name("telegram_custom_emojis_catalog.json")
_RANDOM = "random"
_TEXT_LIMIT = 4096
_CAPTION_LIMIT = 1024
_QUESTION_LIMIT = 300
_EXPLANATION_LIMIT = 200
_MARKS = frozenset("\ufe0f\ufe0e\u200d\u20e3")
_KEYCAP_BASE = frozenset("#*0123456789")
_TAG_RE = re.compile(r"(?is)(</?(?:pre|code|tg-emoji)\b[^>]*>|<[^>]+>)")
_FIELDS = (
    ("text", "parse_mode", "entities", _TEXT_LIMIT),
    ("caption", "parse_mode", "caption_entities", _CAPTION_LIMIT),
    ("question", "question_parse_mode", "question_entities", _QUESTION_LIMIT),
    ("explanation", "explanation_parse_mode", "explanation_entities", _EXPLANATION_LIMIT),
)
_installed: set[int] = set()


class TelegramCustomEmojisSettings(BaseSettings):
    """Enable custom emoji and choose which pack supplies the ids."""

    enabled: bool = False
    # "random", a pack name (StaticEmoji), or "CuteEmoji,StaticEmoji".
    pack: str = _RANDOM
    # "message" picks a pack per outgoing call. "process" picks once.
    random_scope: str = "message"
    # When the chosen pack has no glyph, use one from another pack.
    allow_other_packs: bool = True

    class Config:
        env_prefix = "BOTSPOT_TELEGRAM_CUSTOM_EMOJIS_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class EmojiCatalog:
    def __init__(self, packs: dict[str, dict[str, str]], fallback: dict[str, str]) -> None:
        self.packs = packs
        self.fallback = fallback
        chars = sorted(fallback, key=len, reverse=True)
        self.pattern = re.compile("|".join(re.escape(char) for char in chars)) if chars else None

    def names(self) -> list[str]:
        return list(self.packs)


def _keep(char: str) -> bool:
    """Catalog fallbacks that are emoji, not a bare letter, digit, or ©."""
    if not char or not char.strip():
        return False
    has_mark = any(ch in _MARKS for ch in char)
    for ch in char:
        if ch in _MARKS or ch in _KEYCAP_BASE:
            continue
        if ord(ch) < 0x80:
            return False
        if ord(ch) < 0x2000 and not has_mark:
            return False
    core = "".join(ch for ch in char if ch not in _MARKS)
    if core in _KEYCAP_BASE or core == "":
        return "\u20e3" in char
    return True


def _with_aliases(mapping: dict[str, str]) -> dict[str, str]:
    aliased = dict(mapping)
    for char, emoji_id in mapping.items():
        if "\ufe0f" not in char:
            continue
        stripped = char.replace("\ufe0f", "")
        if stripped and stripped not in aliased and _keep(stripped):
            aliased[stripped] = emoji_id
    return aliased


def export_catalog(source: Path, dest: Path = CATALOG_FILE) -> None:
    """Build the compact pack index from a telegram-emoji catalog.json."""
    raw = json.loads(source.read_text(encoding="utf-8"))
    packs: dict[str, dict[str, str]] = {}
    fallback: dict[str, str] = {}
    fallback_uses: dict[str, int] = {}
    for pack in raw.get("packs", []):
        name = str(pack.get("name") or "").strip()
        if not name:
            continue
        best: dict[str, tuple[int, str]] = {}
        for item in pack.get("emoji", []):
            char = str(item.get("char") or "")
            emoji_id = str(item.get("id") or "")
            if not emoji_id or not _keep(char):
                continue
            uses = int(item.get("uses") or 0)
            current = best.get(char)
            if current is None or uses > current[0]:
                best[char] = (uses, emoji_id)
            previous = fallback_uses.get(char)
            if previous is None or uses > previous:
                fallback[char] = emoji_id
                fallback_uses[char] = uses
        if best:
            packs[name] = {char: emoji_id for char, (_, emoji_id) in best.items()}
    payload = {
        "generated": raw.get("generated"),
        "fallback": _with_aliases(fallback),
        "packs": {name: _with_aliases(mapping) for name, mapping in packs.items()},
    }
    dest.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    logger.info(
        "Wrote custom emoji catalog {} ({} packs, {} glyphs)",
        dest,
        len(payload["packs"]),
        len(payload["fallback"]),
    )


def load_catalog(path: Path = CATALOG_FILE) -> EmojiCatalog:
    data = json.loads(path.read_text(encoding="utf-8"))
    packs = {
        str(name): {str(char): str(emoji_id) for char, emoji_id in mapping.items()}
        for name, mapping in data.get("packs", {}).items()
    }
    fallback = {str(char): str(emoji_id) for char, emoji_id in data.get("fallback", {}).items()}
    return EmojiCatalog(packs, fallback)


class TelegramCustomEmojis:
    def __init__(self, settings: TelegramCustomEmojisSettings, catalog: EmojiCatalog | None = None):
        self.settings = settings
        self.catalog = catalog if catalog is not None else load_catalog()
        self._process_pack: str | None = None
        self._rng = random.Random()

    def pack_names(self) -> list[str]:
        return self.catalog.names()

    def pack_choices(self) -> list[str]:
        raw = (self.settings.pack or _RANDOM).strip()
        known = {name.lower(): name for name in self.catalog.names()}
        if not raw or raw.lower() == _RANDOM:
            return self.catalog.names()
        requested = [part.strip() for part in raw.split(",") if part.strip()]
        found = []
        for name in requested:
            match = known.get(name.lower())
            if match is None:
                logger.warning("Unknown custom emoji pack {!r}; ignoring it", name)
                continue
            if match not in found:
                found.append(match)
        if found:
            return found
        logger.warning("No known custom emoji packs in {!r}; using the full catalog", raw)
        return self.catalog.names()

    def choose_pack(self) -> str:
        choices = self.pack_choices()
        if not choices:
            return ""
        if len(choices) == 1:
            return choices[0]
        scope = (self.settings.random_scope or "message").strip().lower()
        if scope == "process":
            if self._process_pack not in choices:
                self._process_pack = self._rng.choice(choices)
            return self._process_pack
        return self._rng.choice(choices)

    def emoji_id(self, char: str, pack: str) -> str | None:
        pack_map = self.catalog.packs.get(pack, {})
        if char in pack_map:
            return pack_map[char]
        if self.settings.allow_other_packs:
            return self.catalog.fallback.get(char)
        return None

    def apply_html(self, text: str, pack: str) -> str:
        pattern = self.catalog.pattern
        if not text or pattern is None or not pattern.search(text):
            return text

        def replace(segment: str) -> str:
            def one(match: re.Match[str]) -> str:
                emoji_id = self.emoji_id(match.group(0), pack)
                if not emoji_id:
                    return match.group(0)
                return f'<tg-emoji emoji-id="{emoji_id}">{match.group(0)}</tg-emoji>'

            return pattern.sub(one, segment)

        parts = _TAG_RE.split(text)
        skip = {"pre": 0, "code": 0, "tg-emoji": 0}
        out: list[str] = []
        for part in parts:
            lower = part.lower()
            if lower.startswith("<pre"):
                skip["pre"] += 1
                out.append(part)
            elif lower.startswith("</pre"):
                skip["pre"] = max(0, skip["pre"] - 1)
                out.append(part)
            elif lower.startswith("<code"):
                skip["code"] += 1
                out.append(part)
            elif lower.startswith("</code"):
                skip["code"] = max(0, skip["code"] - 1)
                out.append(part)
            elif lower.startswith("<tg-emoji"):
                skip["tg-emoji"] += 1
                out.append(part)
            elif lower.startswith("</tg-emoji"):
                skip["tg-emoji"] = max(0, skip["tg-emoji"] - 1)
                out.append(part)
            elif part.startswith("<"):
                out.append(part)
            elif any(skip.values()):
                out.append(part)
            else:
                out.append(replace(part))
        return "".join(out)

    def apply_entities(
        self, text: str, pack: str, existing: list[Any] | None
    ) -> list[MessageEntity]:
        pattern = self.catalog.pattern
        if not text or pattern is None:
            return []
        covered = _custom_emoji_spans(existing)
        found: list[MessageEntity] = []
        utf16 = 0
        cursor = 0
        for match in pattern.finditer(text):
            utf16 += _utf16_len(text[cursor : match.start()])
            char = match.group(0)
            length = _utf16_len(char)
            emoji_id = self.emoji_id(char, pack)
            end = utf16 + length
            if emoji_id and not _overlaps(utf16, end, covered):
                found.append(
                    MessageEntity(
                        type="custom_emoji",
                        offset=utf16,
                        length=length,
                        custom_emoji_id=emoji_id,
                    )
                )
            utf16 = end
            cursor = match.end()
        return found

    def rewrite(self, method: Any, bot: Bot) -> None:
        if not self.settings.enabled:
            return
        pack = self.choose_pack()
        if not pack:
            return
        for field, parse_field, entity_field, limit in _FIELDS:
            _rewrite_field(self, method, bot, pack, field, parse_field, entity_field, limit)
        media = getattr(method, "media", None)
        if isinstance(media, list):
            for item in media:
                _rewrite_field(
                    self,
                    item,
                    bot,
                    pack,
                    "caption",
                    "parse_mode",
                    "caption_entities",
                    _CAPTION_LIMIT,
                )
        elif media is not None:
            _rewrite_field(
                self, media, bot, pack, "caption", "parse_mode", "caption_entities", _CAPTION_LIMIT
            )
        _rewrite_buttons(self, getattr(method, "reply_markup", None), pack)


def initialize(settings: TelegramCustomEmojisSettings) -> TelegramCustomEmojis:
    try:
        component = TelegramCustomEmojis(settings)
    except FileNotFoundError:
        logger.exception("Custom emoji catalog is missing; leaving unicode emoji in place")
        component = TelegramCustomEmojis(settings, catalog=EmojiCatalog({}, {}))
    if settings.enabled:
        logger.info(
            "Custom Telegram emoji on: pack={!r} scope={} packs={} glyphs={}",
            settings.pack,
            settings.random_scope,
            len(component.pack_names()),
            len(component.catalog.fallback),
        )
    return component


def setup_dispatcher(dp: Any) -> None:
    del dp
    from botspot.core.dependency_manager import DependencyManager

    if not DependencyManager.is_initialized():
        return
    bot = getattr(DependencyManager(), "_bot", None)
    if bot is not None:
        install(bot)


def install(bot: Bot) -> None:
    if id(bot) in _installed:
        return
    bot.session.middleware.register(_middleware)
    _installed.add(id(bot))


async def _middleware(make_request: Any, bot: Bot, method: Any) -> Any:
    component = _active()
    if component is not None:
        try:
            component.rewrite(method, bot)
        except Exception:
            logger.exception("Custom emoji rewrite failed; sending the original text")
    return await make_request(bot, method)


def _active() -> TelegramCustomEmojis | None:
    from botspot.core.dependency_manager import DependencyManager

    if not DependencyManager.is_initialized():
        return None
    component = getattr(DependencyManager(), "_telegram_custom_emojis", None)
    if component is None or not component.settings.enabled:
        return None
    return component


def _resolve_parse_mode(value: Any, bot: Bot) -> Any:
    if isinstance(value, Default):
        default = getattr(bot, "default", None)
        if default is None:
            return None
        return getattr(default, value.name, None)
    return value


def _mode_kind(mode: Any) -> str:
    if mode is None:
        return "plain"
    value = getattr(mode, "value", mode)
    if value == "HTML":
        return "html"
    return "other"


def _rewrite_field(
    component: TelegramCustomEmojis,
    obj: Any,
    bot: Bot,
    pack: str,
    field: str,
    parse_field: str,
    entity_field: str,
    limit: int,
) -> None:
    if obj is None or not hasattr(obj, field) or not hasattr(obj, parse_field):
        return
    text = getattr(obj, field)
    if not isinstance(text, str) or not text:
        return
    kind = _mode_kind(_resolve_parse_mode(getattr(obj, parse_field), bot))
    if kind == "html":
        updated = component.apply_html(text, pack)
        if updated == text:
            return
        if len(updated) > limit:
            logger.warning(
                "Custom emoji expansion of {} is {} chars, over {}; leaving unicode",
                field,
                len(updated),
                limit,
            )
            return
        setattr(obj, field, updated)
        return
    if kind != "plain" or not hasattr(obj, entity_field):
        return
    existing = getattr(obj, entity_field)
    added = component.apply_entities(text, pack, existing)
    if added:
        setattr(obj, entity_field, list(existing or []) + added)


def _rewrite_buttons(component: TelegramCustomEmojis, markup: Any, pack: str) -> None:
    if markup is None:
        return
    rows = getattr(markup, "inline_keyboard", None)
    if rows is None:
        rows = getattr(markup, "keyboard", None)
    if not rows:
        return
    for row in rows:
        for button in row:
            if isinstance(button, str) or not hasattr(button, "text"):
                continue
            if getattr(button, "icon_custom_emoji_id", None):
                continue
            cleaned, emoji_id = _button_icon(component, button.text, pack)
            if emoji_id and cleaned:
                button.text = cleaned
                button.icon_custom_emoji_id = emoji_id


def _button_icon(component: TelegramCustomEmojis, text: str, pack: str) -> tuple[str, str | None]:
    pattern = component.catalog.pattern
    if not isinstance(text, str) or not text or pattern is None:
        return text, None
    first: str | None = None

    def one(match: re.Match[str]) -> str:
        nonlocal first
        emoji_id = component.emoji_id(match.group(0), pack)
        if not emoji_id:
            return match.group(0)
        if first is None:
            first = emoji_id
        return ""

    cleaned = " ".join(pattern.sub(one, text).split())
    if not first or not cleaned:
        return text, None
    return cleaned, first


def _utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _custom_emoji_spans(entities: list[Any] | None) -> list[tuple[int, int]]:
    spans = []
    for entity in entities or []:
        if getattr(entity, "type", None) != "custom_emoji":
            continue
        offset = int(entity.offset)
        spans.append((offset, offset + int(entity.length)))
    return spans


def _overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(not (end <= left or start >= right) for left, right in spans)


__all__ = [
    "CATALOG_FILE",
    "EmojiCatalog",
    "TelegramCustomEmojis",
    "TelegramCustomEmojisSettings",
    "export_catalog",
    "initialize",
    "install",
    "load_catalog",
    "setup_dispatcher",
]
