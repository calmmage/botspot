import re
from typing import Any

from loguru import logger

# Telegram supported HTML tags and their attributes
TELEGRAM_HTML_TAGS = {
    "b": [],  # bold
    "i": [],  # italic
    "u": [],  # underline
    "s": [],  # strikethrough
    "a": ["href"],  # links
    "code": [],  # inline code
    "pre": ["language"],  # code blocks with language
    "tg-spoiler": [],  # spoiler
    "tg-emoji": ["emoji-id"],  # custom emoji
}

try:
    import mistune
    from mistune.renderers.html import HTMLRenderer

    class TelegramHTMLRenderer(HTMLRenderer):
        """Custom HTML renderer that only allows Telegram-supported HTML tags."""

        def __init__(self):
            super().__init__()
            self._allowed_tags = set(TELEGRAM_HTML_TAGS.keys())
            self._allowed_attrs = TELEGRAM_HTML_TAGS

        def text(self, text):
            """Render text."""
            return text

        def block_code(self, code, info=None):
            """Render code blocks with language support."""
            if info:
                return f'<pre language="{info}">{code}</pre>\n'
            # return f'<code>{code}</code>'
            return f"<pre>{code}</pre>\n"

        # def block_quote(self, text):
        #     """Render blockquotes as code blocks."""
        #     # Remove any trailing newlines to avoid extra spacing
        #     # return f'<code>1 - {text}</code>'
        #     return f'<pre>1 - {text}</pre>'

        # def inline_code(self, code):
        #     """Render inline code."""
        #     # return f'<code>{code}</code>'
        #     return f'<pre>3 - {code}</pre>'

        def emphasis(self, text):
            """Render italic text."""
            return f"<i>{text}</i>"

        def strong(self, text):
            """Render bold text."""
            return f"<b>{text}</b>"

        def strikethrough(self, text):
            """Render strikethrough text."""
            return f"<s>{text}</s>"

        def link(self, text, url, title=None):
            """Render links."""
            return f'<a href="{url}">{text}</a>'

        def image(self, alt, url, title=None):
            """Convert images to the same format as hyperlinks."""
            logger.debug(f"Converting image: {alt} -> {url}")
            return f'<a href="{url}">{alt}</a>'

        def heading(self, text: str, level: int, **attrs: Any) -> str:
            """Render headings as bold text."""
            if attrs:
                logger.warning(f"Heading attributes are not supported: {attrs}")
            if level == 1:
                return f"<b>{text.upper()}</b>\n\n"
            elif level == 2:
                return f"<b>{text}</b>\n\n"
            elif level == 3:
                return f"<b>{text}</b>\n"
            elif level == 4:
                return f"{text}\n"
            return f"{text}\n"

        def paragraph(self, text):
            """Render paragraphs as plain text with newlines."""
            return f"{text}\n"

        def linebreak(self):
            """Render line breaks as newlines."""
            return "\n"

        def thematic_break(self):
            """Render horizontal rules as newlines."""
            return "\n"

        def list(self, text: str, ordered: bool, **attrs: Any) -> str:
            """Render lists as plain text with newlines."""

            if attrs:
                logger.warning(f"Heading attributes are not supported: {attrs}")
            lines = text.split("\n")
            if ordered:
                # Split into lines and enumerate starting from 1
                # Filter out empty lines and enumerate
                numbered = [f"{i}. {line}" for i, line in enumerate(lines, 1) if line.strip()]
                return "\n".join(numbered) + "\n"
            else:
                unordered = [f"• {line}" for line in lines if line.strip()]
                return "\n".join(unordered) + "\n"

        def list_item(self, text, **attrs):
            """Render list items as plain text with bullet points."""
            if attrs:
                logger.warning(f"Heading attributes are not supported: {attrs}")
            return f"{text}\n"

    html_pattern = re.compile(r"<[a-zA-Z][^>]*>|</[a-zA-Z][^>]*>")

    def is_html(text: str) -> bool:
        """Check if text contains HTML tags, ignoring tags inside code blocks."""
        # First split by code blocks
        parts = []
        in_code_block = False
        current_part = []

        for line in text.split("\n"):
            if line.startswith("```"):
                if in_code_block:
                    # End of code block
                    parts.append("".join(current_part))
                    current_part = []
                in_code_block = not in_code_block
                continue

            if not in_code_block:
                current_part.append(line + "\n")

        # Add any remaining text
        if current_part:
            parts.append("".join(current_part))

        # Check for HTML tags only in non-code parts
        # Use a more specific pattern that requires a valid HTML tag format
        # This will avoid matching mathematical expressions like "2 < 3"
        return any(bool(html_pattern.search(part)) for part in parts)

    def markdown_to_html(text: str) -> str:
        """
        Convert Markdown text to HTML using only Telegram-supported tags.

        Args:
            text: The markdown text to convert to HTML

        Returns:
            The HTML converted text with only Telegram-supported tags
        """
        # Skip if already HTML
        if is_html(text):
            return text

        # Initialize mistune markdown parser with our custom renderer and strikethrough plugin
        markdown = mistune.create_markdown(
            renderer=TelegramHTMLRenderer(), plugins=["strikethrough"]
        )
        result = markdown(text)
        logger.debug(f"Converting markdown to HTML:\nInput: {text}\nOutput: {result}")
        return str(result)  # Ensure we return a string

    __all__ = ["is_html", "markdown_to_html"]
except ImportError:
    logger.warning(
        "mistune is not installed. HTML rendering will be disabled. "
        "Please install mistune to enable this feature."
    )

    def is_html(text: str) -> bool:
        return False

    def markdown_to_html(text: str) -> str:
        return text
