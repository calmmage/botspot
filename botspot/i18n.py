"""Convenience re-export for botspot i18n."""

from botspot.components.middlewares.i18n import (
    get_lang,
    register_strings,
    set_lang,
    t,
)

__all__ = ["t", "set_lang", "get_lang", "register_strings"]
