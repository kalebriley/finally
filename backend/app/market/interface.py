"""Abstract interface for market data providers."""

from abc import ABC, abstractmethod
from .models import PriceTick


class MarketDataSource(ABC):
    """Abstract base class for all market data implementations.

    Two concrete implementations exist:
    - SimulatorMarketDataSource: GBM-based price simulation (no API key needed)
    - MassiveMarketDataSource: Real data via the Massive (Polygon.io) REST API

    All downstream code is agnostic to which source is active.
    """

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin generating/fetching prices for the given tickers.

        Called once at application startup. The source begins its internal
        update loop — a background asyncio task for the simulator, or a
        polling loop for Massive.
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the update loop and release all resources."""
        ...

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the tracked set.

        The source begins producing prices for this ticker immediately.
        For the simulator, this initialises state and emits an initial tick.
        For Massive, this includes the ticker in the next poll cycle and
        fetches an initial snapshot on-demand.
        """
        ...

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the tracked set.

        The source stops producing prices for this ticker. No-op if the
        ticker is not currently tracked.
        """
        ...

    @abstractmethod
    async def get_price_now(self, ticker: str) -> PriceTick | None:
        """Fetch a fresh price for a single ticker on demand.

        Used for on-demand price seeding when a trade is requested for a
        ticker not currently in the price cache. Returns None if the ticker
        cannot be priced (e.g., network failure for Massive).

        For the simulator: generates a price instantly from its seed table.
        For Massive: makes a synchronous single-ticker snapshot API call.
        """
        ...

    @abstractmethod
    def set_price_callback(self, callback) -> None:
        """Register a callback that receives PriceTick updates.

        Callback signature: async def on_price(tick: PriceTick) -> None

        The source calls this for every price update it generates.
        The PriceCache registers itself as this callback at startup.
        Must be called before start().
        """
        ...
