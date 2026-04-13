"""Data models for the market data subsystem."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class PriceTick:
    """A single raw price update emitted by a MarketDataSource.

    This is the internal contract between data sources and the PriceCache.
    Sources produce PriceTick; the cache derives CachedPrice from it.
    """
    ticker: str
    price: float
    prev_close: float
    timestamp: datetime


@dataclass
class CachedPrice:
    """Derived price data stored in the PriceCache.

    All fields that downstream consumers (SSE stream, trade execution,
    portfolio valuation) need are pre-computed here so reads are cheap.
    """
    ticker: str
    price: float
    prev_price: float       # Previous tick price — used for flash direction
    prev_close: float       # Session/day baseline — used for daily change
    day_change: float       # price - prev_close
    day_change_pct: float   # (price - prev_close) / prev_close * 100
    direction: str          # "up", "down", or "flat" (vs previous tick)
    timestamp: datetime
