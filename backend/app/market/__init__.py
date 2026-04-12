"""Market data subsystem for FinAlly.

Public API:
    PriceTick       — raw tick from a MarketDataSource
    CachedPrice     — derived price data from PriceCache
    MarketDataSource — abstract interface for data sources
    PriceCache      — in-memory price store
    create_market_data_source — factory selecting simulator or Massive
    create_stream_router      — SSE endpoint factory

Typical startup usage:
    cache = PriceCache()
    source = create_market_data_source()
    source.set_price_callback(cache.on_price)
    await source.start(tickers)
"""

from .cache import PriceCache
from .factory import create_market_data_source
from .interface import MarketDataSource
from .models import CachedPrice, PriceTick
from .stream import create_stream_router

__all__ = [
    "CachedPrice",
    "MarketDataSource",
    "PriceTick",
    "PriceCache",
    "create_market_data_source",
    "create_stream_router",
]
