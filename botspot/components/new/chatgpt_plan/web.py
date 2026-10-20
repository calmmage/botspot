"""aiohttp OAuth callback route the host app mounts (only when the flag is on)."""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING, Awaitable, Callable, Optional

from botspot.components.new.chatgpt_plan.errors import PlanError
from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from aiohttp import web

    from botspot.components.new.chatgpt_plan.oauth import LinkResult
    from botspot.components.new.chatgpt_plan.plan import ChatgptPlan

logger = get_logger()

OnLinked = Callable[["LinkResult"], Awaitable[None]]

_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title></head>
<body style="font-family:system-ui,sans-serif;max-width:32rem;margin:3rem auto;padding:0 1rem">
<h1>{title}</h1><p>{body}</p>{link}</body></html>"""


def render_page(title: str, body: str, return_url: str = "", status: int = 200) -> web.Response:
    from aiohttp import web

    link = f'<p><a href="{escape(return_url)}">Telegram</a></p>' if return_url else ""
    html = _PAGE.format(title=escape(title), body=escape(body), link=link)
    return web.Response(text=html, content_type="text/html", status=status)


def make_callback_handler(
    plan: ChatgptPlan, on_linked: Optional[OnLinked] = None
) -> Callable[[web.Request], Awaitable[web.Response]]:
    """Handler for ``GET <callback path>?state=...&code=...``.

    ``on_linked(result)`` lets the host bot message the user after a successful link.
    """
    return_url = plan.settings.return_url

    async def callback(request: web.Request) -> web.Response:
        state = request.query.get("state", "")
        code = request.query.get("code", "")
        if request.query.get("error") or not state or not code:
            return render_page("Not linked", "Linking was cancelled.", return_url, 400)
        try:
            result = await plan.complete_link(state, code)
        except PlanError as error:
            logger.info(f"chatgpt_plan: callback failed: {error.message}")
            return render_page("Not linked", "Link failed, try again.", return_url, 400)
        if on_linked is not None:
            await on_linked(result)
        return render_page("Linked", "ChatGPT plan linked. Go back to Telegram.", return_url)

    return callback


def aiohttp_routes(plan: ChatgptPlan, on_linked: Optional[OnLinked] = None) -> list:
    """Return the aiohttp route def for the OAuth callback (path from ``redirect_uri``)."""
    from aiohttp import web

    return [web.get(plan.settings.callback_path, make_callback_handler(plan, on_linked))]
