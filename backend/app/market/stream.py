"""SSE streaming endpoint for live price updates.

Provides create_stream_router() — a factory that returns a FastAPI APIRouter
containing the GET /stream/prices SSE endpoint. Mount this router in the
main app with prefix="/api" to expose GET /api/stream/prices.

The endpoint pushes all currently cached prices every ~500ms. Version-based
change detection means the HTTP response body only advances when the cache
has been updated since the last send.
"""

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from .cache import PriceCache


def create_stream_router(price_cache: PriceCache) -> APIRouter:
    """Create a FastAPI router with the SSE price stream endpoint.

    Args:
        price_cache: The shared PriceCache instance populated by MarketDataSource.

    Returns:
        APIRouter with GET /stream/prices registered.
    """
    router = APIRouter()

    @router.get("/stream/prices")
    async def price_stream(request: Request) -> EventSourceResponse:
        """Stream live price updates for all tracked tickers via SSE.

        Pushes one JSON event per tracked ticker every ~500ms. Clients
        should use the native EventSource API and handle reconnection
        automatically (EventSource retries by default).

        Event data schema:
            ticker, price, prev_price, prev_close, day_change,
            day_change_pct, direction, timestamp
        """

        async def generate_events() -> AsyncGenerator[dict, None]:
            last_version = -1
            while True:
                if await request.is_disconnected():
                    break

                current_version = price_cache.version
                if current_version != last_version:
                    last_version = current_version
                    prices = price_cache.get_all()
                    for cached in prices.values():
                        yield {
                            "data": json.dumps({
                                "ticker": cached.ticker,
                                "price": cached.price,
                                "prev_price": cached.prev_price,
                                "prev_close": cached.prev_close,
                                "day_change": round(cached.day_change, 4),
                                "day_change_pct": round(cached.day_change_pct, 4),
                                "direction": cached.direction,
                                "timestamp": cached.timestamp.isoformat(),
                            })
                        }

                await asyncio.sleep(0.5)

        return EventSourceResponse(generate_events())

    return router
