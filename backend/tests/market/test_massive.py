"""Tests for MassiveMarketDataSource."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.market.massive_client import MassiveMarketDataSource
from app.market.models import PriceTick


def make_source(**kwargs) -> MassiveMarketDataSource:
    return MassiveMarketDataSource(api_key="test-key", **kwargs)


def _mock_response(data: dict) -> MagicMock:
    """Create a mock httpx Response."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=data)
    return resp


def _snapshot_data(ticker: str, bid: float = 190.80, ask: float = 190.82, prev_close: float = 190.0) -> dict:
    """Build a minimal batch snapshot response body."""
    return {
        "status": "OK",
        "tickers": [
            {
                "ticker": ticker,
                "lastQuote": {"p": bid, "P": ask},
                "prevDay": {"c": prev_close},
            }
        ],
    }


def _single_snapshot_data(ticker: str, bid: float = 190.80, ask: float = 190.82, prev_close: float = 190.0) -> dict:
    return {
        "status": "OK",
        "ticker": {
            "ticker": ticker,
            "lastQuote": {"p": bid, "P": ask},
            "prevDay": {"c": prev_close},
        },
    }


# ---------------------------------------------------------------------------
# _extract_price — static method
# ---------------------------------------------------------------------------


def test_extract_price_from_last_quote_midpoint():
    snapshot = {"lastQuote": {"p": 190.80, "P": 190.82}}
    price = MassiveMarketDataSource._extract_price(snapshot)
    assert abs(price - 190.81) < 0.001


def test_extract_price_prefers_quote_over_trade():
    snapshot = {
        "lastQuote": {"p": 190.80, "P": 190.82},
        "lastTrade": {"p": 191.00},
        "day": {"c": 189.50},
    }
    price = MassiveMarketDataSource._extract_price(snapshot)
    assert abs(price - 190.81) < 0.001


def test_extract_price_from_last_trade_when_no_quote():
    snapshot = {"lastTrade": {"p": 191.00}}
    price = MassiveMarketDataSource._extract_price(snapshot)
    assert price == 191.00


def test_extract_price_prefers_trade_over_day():
    snapshot = {"lastTrade": {"p": 191.00}, "day": {"c": 189.50}}
    price = MassiveMarketDataSource._extract_price(snapshot)
    assert price == 191.00


def test_extract_price_from_day_close_fallback():
    snapshot = {"day": {"c": 189.50}}
    price = MassiveMarketDataSource._extract_price(snapshot)
    assert price == 189.50


def test_extract_price_returns_none_when_no_data():
    price = MassiveMarketDataSource._extract_price({})
    assert price is None


def test_extract_price_returns_none_with_empty_fields():
    snapshot = {"lastQuote": {}, "lastTrade": {}, "day": {}}
    price = MassiveMarketDataSource._extract_price(snapshot)
    assert price is None


# ---------------------------------------------------------------------------
# set_price_callback
# ---------------------------------------------------------------------------


def test_set_price_callback_stores_callback():
    src = make_source()
    callback = AsyncMock()
    src.set_price_callback(callback)
    assert src._callback is callback


# ---------------------------------------------------------------------------
# _poll_snapshots
# ---------------------------------------------------------------------------


async def test_poll_snapshots_fires_callback_for_each_ticker():
    src = make_source()
    received: list[PriceTick] = []

    async def callback(tick: PriceTick) -> None:
        received.append(tick)

    src.set_price_callback(callback)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(_snapshot_data("AAPL")))
    src._client = mock_client
    src._tickers = {"AAPL"}

    await src._poll_snapshots()

    assert len(received) == 1
    assert received[0].ticker == "AAPL"
    assert abs(received[0].price - 190.81) < 0.001


async def test_poll_snapshots_sets_prev_close():
    src = make_source()
    received: list[PriceTick] = []

    async def callback(tick: PriceTick) -> None:
        received.append(tick)

    src.set_price_callback(callback)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(_snapshot_data("AAPL", prev_close=188.00)))
    src._client = mock_client
    src._tickers = {"AAPL"}

    await src._poll_snapshots()
    assert received[0].prev_close == 188.00


async def test_poll_snapshots_ignores_non_ok_status():
    src = make_source()
    callback = AsyncMock()
    src.set_price_callback(callback)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response({"status": "ERROR", "error": "Unknown API Key"}))
    src._client = mock_client
    src._tickers = {"AAPL"}

    await src._poll_snapshots()
    callback.assert_not_called()


async def test_poll_snapshots_skips_when_no_tickers():
    src = make_source()
    callback = AsyncMock()
    src.set_price_callback(callback)
    src._client = AsyncMock()
    src._tickers = set()

    await src._poll_snapshots()
    callback.assert_not_called()
    src._client.get.assert_not_called()


# ---------------------------------------------------------------------------
# _fetch_single_snapshot
# ---------------------------------------------------------------------------


async def test_fetch_single_snapshot_returns_price_tick():
    src = make_source()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(_single_snapshot_data("AAPL")))
    src._client = mock_client

    tick = await src._fetch_single_snapshot("AAPL")
    assert isinstance(tick, PriceTick)
    assert tick.ticker == "AAPL"
    assert abs(tick.price - 190.81) < 0.001


async def test_fetch_single_snapshot_returns_none_on_error_status():
    src = make_source()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response({"status": "ERROR"}))
    src._client = mock_client

    tick = await src._fetch_single_snapshot("AAPL")
    assert tick is None


# ---------------------------------------------------------------------------
# add_ticker / remove_ticker
# ---------------------------------------------------------------------------


async def test_add_ticker_calls_callback():
    src = make_source()
    received: list[PriceTick] = []

    async def callback(tick: PriceTick) -> None:
        received.append(tick)

    src.set_price_callback(callback)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(_single_snapshot_data("TSLA", bid=249.90, ask=250.10)))
    src._client = mock_client

    await src.add_ticker("TSLA")
    assert len(received) == 1
    assert received[0].ticker == "TSLA"


async def test_add_ticker_respects_cap():
    src = make_source(max_tickers=2)
    src._tickers = {"AAPL", "MSFT"}
    src._client = AsyncMock()

    with pytest.raises(ValueError, match="cap"):
        await src.add_ticker("GOOGL")


async def test_add_ticker_idempotent_when_already_tracked():
    src = make_source()
    src._tickers = {"AAPL"}
    callback = AsyncMock()
    src.set_price_callback(callback)
    src._client = AsyncMock()

    await src.add_ticker("AAPL")  # Already in set — should be a no-op
    callback.assert_not_called()


async def test_remove_ticker_removes_from_set():
    src = make_source()
    src._tickers = {"AAPL", "MSFT"}
    await src.remove_ticker("AAPL")
    assert "AAPL" not in src._tickers
    assert "MSFT" in src._tickers


async def test_remove_unknown_ticker_is_noop():
    src = make_source()
    src._tickers = {"AAPL"}
    await src.remove_ticker("UNKNOWN")  # Should not raise
    assert "AAPL" in src._tickers


# ---------------------------------------------------------------------------
# get_price_now
# ---------------------------------------------------------------------------


async def test_get_price_now_returns_price_tick():
    src = make_source()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(_single_snapshot_data("AAPL")))
    src._client = mock_client

    tick = await src.get_price_now("AAPL")
    assert isinstance(tick, PriceTick)
    assert tick.ticker == "AAPL"
