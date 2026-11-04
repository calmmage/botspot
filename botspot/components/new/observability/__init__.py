"""Persistent telemetry, owner dashboard and lifecycle integration."""

from __future__ import annotations

import asyncio
import platform
from contextlib import suppress
from datetime import UTC, datetime

from aiogram import BaseMiddleware, F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from loguru import logger

from botspot.observability.client import ObservabilityClient

from .auth import OwnerAuth
from .registration import dashboard_url, register_owner_menu
from .settings import ObservabilitySettings


class Observability:
    def __init__(self, settings, database, bot, admins):
        self.settings = settings
        self.bot = bot
        self.admins = admins
        self.auth = OwnerAuth(
            bot.token,
            admins,
            settings.token.get_secret_value(),
            max_age=settings.auth_max_age,
            session_ttl=settings.session_ttl,
        )
        self.client = ObservabilityClient(
            database,
            str(bot.id),
            metrics=settings.metrics,
            dimensions=settings.dimensions,
            secrets=(
                bot.token,
                settings.token.get_secret_value(),
                settings.mongo_url.get_secret_value(),
                settings.registry_mongo_url.get_secret_value(),
            ),
        )
        self._owned_clients = []
        self._sink_id = None
        self._heartbeat_task = None
        self._runner = None
        self._app = None
        self._registered = set()
        self.auth.on_owner_authenticated = self._register_identity
        if settings.registry_mongo_url.get_secret_value():
            from pymongo import AsyncMongoClient

            mongo = AsyncMongoClient(
                settings.registry_mongo_url.get_secret_value(), serverSelectionTimeoutMS=2000
            )
            self._owned_clients.append(mongo)
            self.client.registry_database = mongo[settings.registry_mongo_database]

    async def record_error(self, **fields):
        await self.client.record_error(**fields)

    def mount(self, app):
        """Mount on the host's existing aiohttp application before it is frozen."""
        from .dashboard import aiohttp_routes

        if self._app is not None:
            raise RuntimeError("Observability routes already mounted")
        app.add_routes(aiohttp_routes(self.client, self.auth))
        self._app = app

    async def _register_identity(self, user):
        identity = user.model_dump() if hasattr(user, "model_dump") else dict(user)
        user_id = identity.get("id")
        if (
            self.settings.public_url
            and self.auth.is_owner(identity)
            and user_id not in self._registered
        ):
            registered = await self.client.run_safely(
                register_owner_menu(self.bot, [str(user_id)], self.settings.public_url),
                "owner menu",
            )
            if registered:
                self._registered.add(user_id)

    async def heartbeat(self):
        from botspot import __version__

        owners = [
            f"id:{a}" if a.isdigit() else f"username:{a.lstrip('@').lower()}"
            for a in (str(v).strip() for v in self.admins)
        ]
        await self.client.run_safely(
            self.client.registry_database["botspot_bot_registry"].update_one(
                {"bot_id": self.bot.id},
                {
                    "$set": {
                        "bot_id": self.bot.id,
                        "username": self.client.bot_name,
                        "dashboard_url": dashboard_url(self.settings.public_url),
                        "version": __version__,
                        "host": platform.node(),
                        "owners": owners,
                        "last_heartbeat": datetime.now(UTC),
                    }
                },
                upsert=True,
            ),
            "heartbeat",
        )

    async def _heartbeat(self):
        while True:
            await asyncio.sleep(300)
            await self.heartbeat()

    async def startup(self, bot=None):
        me = await self.bot.get_me()
        self.client.bot_name = me.username or str(me.id)
        await self.client.run_safely(
            self.client.ensure_indexes(self.settings.retention_days), "indexes"
        )
        self._sink_id = logger.add(self.client.sink, level="INFO", loop=asyncio.get_running_loop())
        if self._app is None:
            await self.client.run_safely(self._start_server(), "dashboard server")
        if self.settings.public_url:
            registered = await self.client.run_safely(
                register_owner_menu(self.bot, self.admins, self.settings.public_url), "owner menus"
            )
            if registered:
                self._registered.update(int(a) for a in self.admins if str(a).isdigit())
            await self.heartbeat()
            self._heartbeat_task = asyncio.create_task(self._heartbeat())
        else:
            logger.info(
                "Observability persists locally; owner buttons not registered: "
                "BOTSPOT_OBSERVABILITY_PUBLIC_URL is unset (HTTPS required)"
            )

    async def _start_server(self):
        from aiohttp import web

        app = web.Application()
        self.mount(app)
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        await web.TCPSite(self._runner, self.settings.host, self.settings.port).start()

    async def shutdown(self, **kwargs):
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.client.run_safely(self._heartbeat_task, "heartbeat stop")
        await self.client.run_safely(logger.complete(), "log drain")
        if self._sink_id is not None:
            logger.remove(self._sink_id)
        if self._runner is not None:
            await self.client.run_safely(self._runner.cleanup(), "server cleanup")
        for mongo in self._owned_clients:
            await self.client.run_safely(mongo.close(), "Mongo close")

    def owner_button(self, page):
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Open " + page,
                        web_app=WebAppInfo(url=dashboard_url(self.settings.public_url, page)),
                    )
                ]
            ]
        )

    def setup_dispatcher(self, dp):
        from .middleware import setup_dispatcher

        setup_dispatcher(dp, self.client)
        component = self

        class RegisterOwner(BaseMiddleware):
            async def __call__(self, handler, event, data):
                user = data.get("event_from_user")
                chat = data.get("event_chat")
                if user and chat and chat.type == "private":
                    await component._register_identity(user)
                return await handler(event, data)

        dp.update.outer_middleware(RegisterOwner())
        router = Router(name="botspot_observability")

        async def owner_filter(message):
            return bool(
                message.from_user
                and message.chat.type == "private"
                and self.auth.is_owner(message.from_user.model_dump())
            )

        async def open_dashboard(message):
            page = "logs" if message.text.split()[0].split("@")[0] == "/logs" else "dashboard"
            await message.answer("Open your bot dashboard.", reply_markup=self.owner_button(page))

        if self.settings.public_url:
            router.message.register(
                open_dashboard, Command("dashboard", "logs"), F.chat.type == "private", owner_filter
            )
        # Owner commands must precede application catch-all handlers.
        dp.include_router(router)
        dp.sub_routers.insert(0, dp.sub_routers.pop())
        dp.startup.register(self.startup)
        dp.shutdown.register(self.shutdown)


def initialize(settings, deps):
    """Reuse the bot database, or an explicitly configured observability database."""
    if not settings.enabled:
        return None
    mongo = None
    if settings.mongo_url.get_secret_value():
        from pymongo import AsyncMongoClient

        mongo = AsyncMongoClient(
            settings.mongo_url.get_secret_value(), serverSelectionTimeoutMS=2000
        )
        database = mongo[settings.mongo_database]
    else:
        database = deps._mongo_database
    if database is None or deps._bot is None:
        logger.warning(
            "Observability enabled but no Mongo database/bot configured; "
            "enable BOTSPOT_MONGO_DATABASE_ENABLED or set BOTSPOT_OBSERVABILITY_MONGO_URL"
        )
        return None
    component = Observability(settings, database, deps.bot, deps.botspot_settings.admins)
    if mongo is not None:
        component._owned_clients.append(mongo)
    return component


__all__ = ["Observability", "ObservabilitySettings", "initialize"]
