"""Access control: warn about the env var only when the MongoDB list actually differs."""

import pytest
from loguru import logger

from botspot.components.data.access_control import (
    diff_access_lists,
    get_access_control,
)
from tests.telegram import BotClient


def test_diff_same_lists():
    diff = diff_access_lists(["@alice", "@bob"], ["@alice", "@bob"])
    assert diff.same
    assert diff.only_in_db == [] and diff.only_in_env == []


def test_diff_extra_in_db():
    diff = diff_access_lists(["@alice", "@bob", "@carol"], ["@alice", "@bob"])
    assert not diff.same
    assert diff.only_in_db == ["@carol"]
    assert diff.only_in_env == []


def test_diff_missing_in_db():
    diff = diff_access_lists(["@alice"], ["@alice", "@bob"])
    assert not diff.same
    assert diff.only_in_db == []
    assert diff.only_in_env == ["@bob"]


def test_diff_normalises_at_sign_case_and_numeric_ids():
    diff = diff_access_lists(["Alice", " @BOB ", 12345], ["@alice", "bob", "12345"])
    assert diff.same


def test_diff_keeps_original_spelling():
    diff = diff_access_lists(["@Carol"], ["dave"])
    assert diff.only_in_db == ["@Carol"]
    assert diff.only_in_env == ["dave"]


def test_diff_env_unset_lists_everything_as_only_in_db():
    diff = diff_access_lists(["@alice"], [])
    assert not diff.same
    assert diff.only_in_db == ["@alice"]


class _LogSink:
    def __init__(self) -> None:
        self.records: list = []

    def __call__(self, message) -> None:
        self.records.append(message.record)

    def lines(self, level: str) -> list[str]:
        return [r["message"] for r in self.records if r["level"].name == level]


@pytest.fixture
def log_sink():
    sink = _LogSink()
    handler_id = logger.add(sink, level="INFO")
    yield sink
    logger.remove(handler_id)


def _client_with_db_lists(friends_db, admins_db, **botspot) -> BotClient:
    client = BotClient(mongo=True, access_control={"enabled": True}, **botspot)
    col = client.mongo.get_collection("access_control")
    col.docs.append({"_id": "friends", "values": friends_db})
    col.docs.append({"_id": "admins", "values": admins_db})
    return client


@pytest.mark.asyncio
async def test_get_friends_identical_lists_do_not_warn(log_sink):
    client = _client_with_db_lists(
        ["@alice", "@bob"], ["@admin"], friends_str="@alice,@bob", admins_str="@admin"
    )
    await client.emit_startup()

    assert log_sink.lines("WARNING") == []
    infos = log_sink.lines("INFO")
    assert "Loaded 2 friends from MongoDB (matches BOTSPOT_FRIENDS_STR)" in infos
    assert "Loaded 1 admins from MongoDB (matches BOTSPOT_ADMINS_STR)" in infos

    report = get_access_control().get_access_report()
    assert report["friends"] == {
        "source": "mongo",
        "count": 2,
        "only_in_db": [],
        "only_in_env": [],
    }
    assert report["admins"]["source"] == "mongo"


@pytest.mark.asyncio
async def test_get_friends_different_lists_warn_once_with_names(log_sink):
    client = _client_with_db_lists(
        ["@alice", "@bob"], ["@admin"], friends_str="@alice,@carol", admins_str="@admin"
    )
    await client.emit_startup()

    warnings = log_sink.lines("WARNING")
    assert len(warnings) == 1
    assert warnings[0] == (
        "Friends list from MongoDB differs from BOTSPOT_FRIENDS_STR — "
        "only in MongoDB: @bob; only in env: @carol. MongoDB wins."
    )

    report = get_access_control().get_access_report()
    assert report["friends"]["only_in_db"] == ["@bob"]
    assert report["friends"]["only_in_env"] == ["@carol"]
    assert report["admins"]["only_in_db"] == [] and report["admins"]["only_in_env"] == []


@pytest.mark.asyncio
async def test_get_admins_extra_admin_in_db_warns_with_name(log_sink):
    client = _client_with_db_lists(
        ["@alice"], ["@admin", "@extra"], friends_str="@alice", admins_str="@admin"
    )
    await client.emit_startup()

    warnings = log_sink.lines("WARNING")
    assert warnings == [
        "Admins list from MongoDB differs from BOTSPOT_ADMINS_STR — "
        "only in MongoDB: @extra. MongoDB wins."
    ]


@pytest.mark.asyncio
async def test_env_unset_is_info_only(log_sink):
    client = _client_with_db_lists(["@alice", "@bob"], ["@admin"], admins_str="@admin")
    await client.emit_startup()

    assert log_sink.lines("WARNING") == []
    assert "Loaded 2 friends from MongoDB (BOTSPOT_FRIENDS_STR unset)" in log_sink.lines("INFO")
    report = get_access_control().get_access_report()
    assert report["friends"] == {
        "source": "mongo",
        "count": 2,
        "only_in_db": [],
        "only_in_env": [],
    }


@pytest.mark.asyncio
async def test_no_db_data_falls_back_to_env_source(log_sink):
    client = BotClient(
        mongo=True,
        access_control={"enabled": True},
        friends_str="@alice",
        admins_str="@admin",
    )
    await client.emit_startup()

    assert log_sink.lines("WARNING") == []
    report = get_access_control().get_access_report()
    assert report["friends"]["source"] == "env"
    assert report["friends"]["count"] == 1
    assert report["admins"]["source"] == "env"
