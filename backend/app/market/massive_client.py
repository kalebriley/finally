"""Massive (Polygon.io) market data source.

Polls the Massive REST API for real stock prices. Uses the batch snapshot
endpoint (single API call for all tickers) to stay within the free-tier
rate limit of 5 calls/minute.

Free tier:
  - 5 calls/minute total
  - Poll all tickers every 12 seconds (= 5 calls/min)
  - Maximum 25 tracked tickers (to prevent staleness from degrading UX)

Paid tiers can reduce poll_interval (e.g., 2–5 seconds) for near-realtime
updates — just set a smaller poll_interval when constructing this class.
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from .interface import MarketDataSource
from .models import PriceTick

logger = logging.getLogger(__name__)

BASE_URL = "https://api.massive.com"
FREE_TIER_POLL_INTERVAL: float = 12.0  # seconds (5 calls/min budget)
FREE_TIER_MAX_TICKERS: int = 25


class MassiveMarketDataSource(MarketDataSource):
    """Market data source backed by the Massive (Polygon.io) REST API.

    Args:
        api_key: Massive API key (required).
        poll_interval: Seconds between batch snapshot polls. Default: 12s (free tier).
        max_tickers: Maximum number of tickers to track. Default: 25 (free tier).
    """

    def __init__(
        self,
        api_key: str,
        poll_interval: float = FREE_TIER_POLL_INTERVAL,
        max_tickers: int = FREE_TIER_MAX_TICKERS,
    ) -> None:
        self._api_key = api_key
        self._poll_interval = poll_interval
        self._max_tickers = max_tickers
        self._tickers: set[str] = set()
        self._callback = None
        self._task: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None

    def set_price_callback(self, callback) -> None:
        self._callback = callback

    async def start(self, tickers: list[str]) -> None:
        """Start the polling loop after fetching an initial batch snapshot."""
        self._tickers = set(tickers)
        self._client = httpx.AsyncClient(timeout=10.0)
        # Populate cache immediately before the first poll interval elapses
        await self._poll_snapshots()
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Cancel the polling loop and close the HTTP client."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._client:
            await self._client.aclose()
            self._client = None

    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker, fetch its initial price, and fire the callback.

        Raises:
            ValueError: If adding the ticker would exceed the free-tier cap.
        """
        if ticker in self._tickers:
            return  # Already tracked — idempotent
        if len(self._tickers) >= self._max_tickers:
            raise ValueError(
                f"Ticker cap of {self._max_tickers} reached. "
                f"Cannot track {ticker} in Massive mode on the free tier. "
                "Remove a ticker first or upgrade to a paid plan."
            )
        self._tickers.add(ticker)
        tick = await self._fetch_single_snapshot(ticker)
        if tick and self._callback:
            await self._callback(tick)

    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the tracked set. No-op if not tracked."""
        self._tickers.discard(ticker)

    async def get_price_now(self, ticker: str) -> PriceTick | None:
        """Fetch a fresh price for one ticker on demand (for trade seeding)."""
        return await self._fetch_single_snapshot(ticker)

    # ------------------------------------------------------------------
    # Internal polling helpers
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        """Repeatedly poll the batch snapshot endpoint at poll_interval."""
        while True:
            await asyncio.sleep(self._poll_interval)
            try:
                await self._poll_snapshots()
            except Exception as exc:
                logger.warning("Batch snapshot poll failed: %s", exc)

    async def _poll_snapshots(self) -> None:
        """Fetch a batch snapshot for all tracked tickers and fire callbacks."""
        if not self._tickers or not self._client:
            return

        ticker_str = ",".join(sorted(self._tickers))
        url = f"{BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers"
        params = {"tickers": ticker_str, "apiKey": self._api_key}

        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Snapshot request failed: %s", exc)
            return

        if data.get("status") != "OK":
            logger.warning(
                "Snapshot API error — status: %s, error: %s",
                data.get("status"),
                data.get("error"),
            )
            return

        now = datetime.now(timezone.utc)
        for t in data.get("tickers", []):
            ticker = t.get("ticker")
            if not ticker:
                continue
            price = self._extract_price(t)
            if price is None:
                continue

            prev_day = t.get("prevDay") or {}
            prev_close = prev_day.get("c") or price

            tick = PriceTick(
                ticker=ticker,
                price=price,
                prev_close=prev_close,
                timestamp=now,
            )
            if self._callback:
                await self._callback(tick)

    async def _fetch_single_snapshot(self, ticker: str) -> PriceTick | None:
        """Fetch a snapshot for a single ticker (on-demand seeding or add_ticker)."""
        client = self._client
        close_after = False
        if client is None:
            # start() not yet called — create a temporary client
            client = httpx.AsyncClient(timeout=10.0)
            close_after = True

        try:
            url = f"{BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"
            params = {"apiKey": self._api_key}
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Single snapshot failed for %s: %s", ticker, exc)
            return None
        finally:
            if close_after:
                await client.aclose()

        if data.get("status") != "OK":
            logger.warning("Single snapshot error for %s: %s", ticker, data.get("error"))
            return None

        t = data.get("ticker") or {}
        price = self._extract_price(t)
        if price is None:
            return None

        prev_day = t.get("prevDay") or {}
        prev_close = prev_day.get("c") or price

        return PriceTick(
            ticker=ticker,
            price=price,
            prev_close=prev_close,
            timestamp=datetime.now(timezone.utc),
        )

    @staticmethod
    def _extract_price(snapshot: dict) -> float | None:
        """Extract the best available price from a snapshot object.

        Priority order:
        1. lastQuote midpoint (bid + ask) / 2  — most accurate, paid tiers
        2. lastTrade price                     — last executed trade
        3. day.c (day close)                   — free-tier fallback
        """
        last_quote = snapshot.get("lastQuote") or {}
        bid = last_quote.get("p")
        ask = last_quote.get("P")
        if bid and ask:
            return (bid + ask) / 2

        last_trade = snapshot.get("lastTrade") or {}
        trade_price = last_trade.get("p")
        if trade_price:
            return trade_price

        day = snapshot.get("day") or {}
        day_close = day.get("c")
        if day_close:
            return day_close

        return None
