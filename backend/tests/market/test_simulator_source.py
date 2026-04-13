"""Integration tests for SimulatorMarketDataSource lifecycle."""

import asyncio
import random
from datetime import datetime, timezone

from app.market.models import PriceTick
from app.market.simulator import SimulatorMarketDataSource


def make_source(seed: int = 42) -> SimulatorMarketDataSource:
    return SimulatorMarketDataSource(rng=random.Random(seed))


# ---------------------------------------------------------------------------
# Lifecycle: start / stop
# ---------------------------------------------------------------------------


async def test_start_initialises_all_tickers():
    src = make_source()
    tickers = ["AAPL", "MSFT", "GOOGL"]
    await src.start(tickers)
    try:
        assert set(src.get_tickers()) == set(tickers)
    finally:
        await src.stop()


async def test_start_creates_background_task():
    src = make_source()
    await src.start(["AAPL"])
    try:
        assert src._task is not None
        assert not src._task.done()
    finally:
        await src.stop()


async def test_stop_cancels_task():
    src = make_source()
    await src.start(["AAPL"])
    task = src._task
    await src.stop()
    assert task.done()
    assert src._task is None


async def test_stop_when_not_started_is_safe():
    src = make_source()
    await src.stop()  # Should not raise


# ---------------------------------------------------------------------------
# add_ticker / remove_ticker
# ---------------------------------------------------------------------------


async def test_add_ticker_is_tracked():
    src = make_source()
    await src.start([])
    try:
        await src.add_ticker("AAPL")
        assert "AAPL" in src.get_tickers()
    finally:
        await src.stop()


async def test_add_ticker_fires_callback():
    src = make_source()
    received: list[PriceTick] = []

    async def callback(tick: PriceTick) -> None:
        received.append(tick)

    src.set_price_callback(callback)
    await src.start([])
    try:
        await src.add_ticker("AAPL")
        assert len(received) == 1
        assert received[0].ticker == "AAPL"
    finally:
        await src.stop()


async def test_add_ticker_idempotent():
    """Adding the same ticker twice should not raise or duplicate state."""
    src = make_source()
    received: list[PriceTick] = []

    async def callback(tick: PriceTick) -> None:
        received.append(tick)

    src.set_price_callback(callback)
    await src.start([])
    try:
        await src.add_ticker("AAPL")
        await src.add_ticker("AAPL")  # Re-adding fires callback again but doesn't duplicate state
        assert src.get_tickers().count("AAPL") == 1
    finally:
        await src.stop()


async def test_remove_ticker_removes_from_tracked():
    src = make_source()
    await src.start(["AAPL"])
    try:
        await src.remove_ticker("AAPL")
        assert "AAPL" not in src.get_tickers()
    finally:
        await src.stop()


async def test_remove_unknown_ticker_is_noop():
    src = make_source()
    await src.start([])
    try:
        await src.remove_ticker("UNKNOWN")  # Should not raise
    finally:
        await src.stop()


# ---------------------------------------------------------------------------
# get_price_now
# ---------------------------------------------------------------------------


async def test_get_price_now_returns_price_tick():
    src = make_source()
    await src.start(["AAPL"])
    try:
        tick = await src.get_price_now("AAPL")
        assert isinstance(tick, PriceTick)
        assert tick.ticker == "AAPL"
        assert tick.price > 0
    finally:
        await src.stop()


async def test_get_price_now_initialises_unknown_ticker():
    src = make_source()
    await src.start([])
    try:
        tick = await src.get_price_now("PYPL")
        assert isinstance(tick, PriceTick)
        assert tick.price > 0
        assert "PYPL" in src.get_tickers()
    finally:
        await src.stop()


# ---------------------------------------------------------------------------
# Callback fires during the main loop
# ---------------------------------------------------------------------------


async def test_callback_fires_during_loop():
    """Run the simulator briefly and verify the callback fires."""
    src = SimulatorMarketDataSource(rng=random.Random(1))
    received: list[PriceTick] = []

    async def callback(tick: PriceTick) -> None:
        received.append(tick)

    src.set_price_callback(callback)
    await src.start(["AAPL"])
    try:
        # Wait for at least one full tick (TICK_INTERVAL = 0.5s, wait 0.6s)
        await asyncio.sleep(0.6)
        assert len(received) >= 1
        assert all(t.ticker == "AAPL" for t in received)
    finally:
        await src.stop()
