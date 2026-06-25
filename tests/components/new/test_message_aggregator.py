import asyncio
import datetime
from types import SimpleNamespace

import pytest

from botspot.components.new.message_aggregator import (
    MessageAggregator,
    MessageAggregatorSettings,
)


def _msg(i, uid=1, text="hi"):
    base = datetime.datetime(2026, 1, 1, 0, 0, 0)
    return SimpleNamespace(
        message_id=i,
        date=base + datetime.timedelta(seconds=i),
        text=text,
        from_user=SimpleNamespace(id=uid),
        chat=SimpleNamespace(id=uid),
    )


@pytest.mark.asyncio
async def test_burst_collapses_to_single_ordered_batch():
    agg = MessageAggregator(MessageAggregatorSettings(enabled=True, delay=0.1))
    # 4 messages of one burst arrive ~together (out of order)
    results = await asyncio.gather(*[agg.collect(_msg(i)) for i in [2, 0, 3, 1]])
    batches = [r for r in results if r is not None]
    assert len(batches) == 1, "exactly one call should own the batch"
    assert len(batches[0]) == 4
    assert [m.message_id for m in batches[0]] == [0, 1, 2, 3], "batch must be time-ordered"
    assert results.count(None) == 3, "the other three calls return None"


@pytest.mark.asyncio
async def test_separate_users_get_separate_batches():
    agg = MessageAggregator(MessageAggregatorSettings(enabled=True, delay=0.1))
    a, b = await asyncio.gather(agg.collect(_msg(0, uid=1)), agg.collect(_msg(0, uid=2)))
    assert a is not None and b is not None
    assert len(a) == 1 and len(b) == 1


@pytest.mark.asyncio
async def test_command_burst_is_released():
    agg = MessageAggregator(MessageAggregatorSettings(enabled=True, delay=0.1))
    (res,) = await asyncio.gather(agg.collect(_msg(0, text="/start")))
    assert res is None, "a burst starting with a command is left for command handlers"
