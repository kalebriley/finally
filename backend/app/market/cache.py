"""In-memory price cache for the market data subsystem."""

from datetime import datetime
from typing import Optional

from .models import CachedPrice, PriceTick


class PriceCache:
    """Central in-memory store of the latest price for each tracked ticker.

    All market data consumers (SSE stream, trade execution, portfolio
    valuation) read from this cache. The active MarketDataSource writes
    to it via the on_price callback.

    The version counter increments on every update and is used by the SSE
    stream for change detection — the stream only needs to push when the
    version has advanced.

    Single-threaded asyncio model: no lock needed since on_price() contains
    no await points, making all dict operations atomic within the event loop.
    """

    def __init__(self) -> None:
        self._prices: dict[str, CachedPrice] = {}
        self._version: int = 0

    async def on_price(self, tick: PriceTick) -> None:
        """Callback registered with MarketDataSource.

        Receives a raw PriceTick, derives all computed fields, and stores
        a CachedPrice. Also increments the version counter.
        """
        existing = self._prices.get(tick.ticker)
        prev_price = existing.price if existing else tick.price

        if tick.prev_close and tick.prev_close != 0:
            day_change = tick.price - tick.prev_close
            day_change_pct = day_change / tick.prev_close * 100
        else:
            day_change = 0.0
            day_change_pct = 0.0

        if tick.price > prev_price:
            direction = "up"
        elif tick.price < prev_price:
            direction = "down"
        else:
            direction = "flat"

        self._prices[tick.ticker] = CachedPrice(
            ticker=tick.ticker,
            price=tick.price,
            prev_price=prev_price,
            prev_close=tick.prev_close,
            day_change=day_change,
            day_change_pct=day_change_pct,
            direction=direction,
            timestamp=tick.timestamp,
        )
        self._version += 1

    def get(self, ticker: str) -> Optional[CachedPrice]:
        """Return the latest cached price for a ticker, or None."""
        return self._prices.get(ticker)

    def get_price(self, ticker: str) -> Optional[float]:
        """Return the latest price float for a ticker, or None."""
        cached = self._prices.get(ticker)
        return cached.price if cached else None

    def get_all(self) -> dict[str, CachedPrice]:
        """Return a snapshot of all currently cached prices."""
        return dict(self._prices)

    def remove(self, ticker: str) -> None:
        """Remove a ticker from the cache (called when ticker is no longer tracked)."""
        self._prices.pop(ticker, None)

    @property
    def version(self) -> int:
        """Monotonically increasing counter; increments on every price update."""
        return self._version
