"""Simple dict-based i18n for 2+ languages (en/ru)."""

from contextvars import ContextVar
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from pydantic_settings import BaseSettings

_current_lang: ContextVar[str] = ContextVar("_current_lang", default="en")
_STRINGS: dict[str, dict[str, str]] = {}
_botspot_strings_loaded: bool = False


class I18nSettings(BaseSettings):
    enabled: bool = True
    default_locale: str = "en"

    class Config:
        env_prefix = "BOTSPOT_I18N_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def set_lang(lang: str) -> None:
    _current_lang.set(lang)


def get_lang() -> str:
    return _current_lang.get()


def _ensure_botspot_strings() -> None:
    global _botspot_strings_loaded
    if not _botspot_strings_loaded:
        _botspot_strings_loaded = True
        from botspot.components.middlewares.i18n_strings import BOTSPOT_STRINGS

        _STRINGS.update(BOTSPOT_STRINGS)


def t(_key: str, /, **kwargs: Any) -> str:
    """Get translated string by key, formatted with kwargs."""
    _ensure_botspot_strings()
    lang = _current_lang.get()
    entry = _STRINGS.get(_key)
    if entry is None:
        return _key
    text = entry.get(lang) or entry.get("en", _key)
    if kwargs:
        text = text.format(**kwargs)
    return text


def register_strings(strings: dict[str, dict[str, str]]) -> None:
    """Merge app-specific strings into the global registry."""
    _STRINGS.update(strings)


def _resolve_locale(event: TelegramObject, default: str = "en") -> str:
    """Extract locale from Telegram event's from_user.language_code."""
    from_user = getattr(event, "from_user", None)
    if from_user is None:
        # Try nested: callback_query.message doesn't have from_user directly
        message = getattr(event, "message", None)
        if message is not None:
            from_user = getattr(message, "from_user", None)
    if from_user is not None:
        lang_code = getattr(from_user, "language_code", None)
        if lang_code and lang_code.startswith("ru"):
            return "ru"
    return default


class I18nMiddleware(BaseMiddleware):
    """Middleware that sets the language context for each update."""

    def __init__(
        self,
        default_locale: str = "en",
        locale_resolver: Optional[Callable[[TelegramObject], Optional[str]]] = None,
    ):
        self.default_locale = default_locale
        self.locale_resolver = locale_resolver

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Custom resolver takes priority (e.g. user settings in whisper-bot)
        locale = None
        if self.locale_resolver is not None:
            locale = self.locale_resolver(event)
        if locale is None:
            locale = _resolve_locale(event, self.default_locale)
        set_lang(locale)
        return await handler(event, data)
