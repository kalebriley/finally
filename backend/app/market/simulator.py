"""Market data simulator using Geometric Brownian Motion (GBM).

Implements MarketDataSource with no external dependencies. Generates
realistic-looking price streams for all tracked tickers at ~500ms intervals,
with correlated moves within sectors and occasional random "event" shocks.
"""

import asyncio
import math
import random
from datetime import datetime, timezone

from .interface import MarketDataSource
from .models import PriceTick
from .seed_prices import (
    DEFAULT_SEED,
    DRIFT,
    EVENT_MAGNITUDE_MAX,
    EVENT_MAGNITUDE_MIN,
    EVENT_PROBABILITY,
    SECONDS_PER_TRADING_YEAR,
    SECTOR_CORRELATION,
    TICK_INTERVAL,
    TICKER_SEEDS,
)


class _TickerState:
    """Mutable simulation state for a single ticker."""

    __slots__ = ("price", "prev_close", "volatility", "sector")

    def __init__(self, price: float, prev_close: float, volatility: float, sector: str) -> None:
        self.price = price
        self.prev_close = prev_close
        self.volatility = volatility
        self.sector = sector


class SimulatorMarketDataSource(MarketDataSource):
    """GBM-based market data simulator.

    Each tick:
      new_price = price * (1 + drift * dt + volatility * sqrt(dt) * Z)

    where Z is a correlated normal random variable combining a sector-wide
    factor and an idiosyncratic factor:
      Z = corr * Z_sector + sqrt(1 - corr²) * Z_idio

    Prices are rounded to 2 decimal places and clamped above $0.01.

    Args:
        rng: Optional random.Random instance. Provide a seeded instance for
             deterministic tests; omit for production use.
    """

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng: random.Random = rng or random.Random()
        self._tickers: dict[str, _TickerState] = {}
        self._callback = None
        self._task: asyncio.Task | None = None

    def set_price_callback(self, callback) -> None:
        self._callback = callback

    async def start(self, tickers: list[str]) -> None:
        """Initialise all tickers and start the background update loop."""
        for ticker in tickers:
            self._init_ticker(ticker)
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Cancel the update loop and wait for it to finish."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker and emit an initial price tick immediately."""
        if ticker not in self._tickers:
            self._init_ticker(ticker)

        state = self._tickers[ticker]
        tick = PriceTick(
            ticker=ticker,
            price=state.price,
            prev_close=state.prev_close,
            timestamp=datetime.now(timezone.utc),
        )
        if self._callback:
            await self._callback(tick)

    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the simulation. No-op if not tracked."""
        self._tickers.pop(ticker, None)

    async def get_price_now(self, ticker: str) -> PriceTick | None:
        """Return the current price for a ticker (initialises it if unknown)."""
        if ticker not in self._tickers:
            self._init_ticker(ticker)
        state = self._tickers[ticker]
        return PriceTick(
            ticker=ticker,
            price=state.price,
            prev_close=state.prev_close,
            timestamp=datetime.now(timezone.utc),
        )

    def get_tickers(self) -> list[str]:
        """Return the list of currently tracked tickers."""
        return list(self._tickers.keys())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_ticker(self, ticker: str) -> None:
        """Initialise a ticker's state from the seed table or defaults."""
        seed = TICKER_SEEDS.get(ticker, DEFAULT_SEED)
        self._tickers[ticker] = _TickerState(
            price=seed["price"],
            prev_close=seed["price"],  # Fixed at seed — resets on container restart
            volatility=seed["volatility"],
            sector=seed["sector"],
        )

    def _step_price(self, state: _TickerState, dt: float, z: float) -> None:
        """Apply one GBM step in-place to the ticker's state."""
        state.price *= 1 + DRIFT * dt + state.volatility * math.sqrt(dt) * z
        state.price = max(round(state.price, 2), 0.01)

    def _apply_event(self, state: _TickerState) -> None:
        """Apply a sudden 2–5% move in a random direction."""
        magnitude = self._rng.uniform(EVENT_MAGNITUDE_MIN, EVENT_MAGNITUDE_MAX)
        sign = self._rng.choice([-1, 1])
        state.price = max(round(state.price * (1 + magnitude * sign), 2), 0.01)

    async def _run_loop(self) -> None:
        """Main simulation loop — updates all tickers every TICK_INTERVAL seconds."""
        dt = TICK_INTERVAL / SECONDS_PER_TRADING_YEAR

        while True:
            await asyncio.sleep(TICK_INTERVAL)
            now = datetime.now(timezone.utc)

            # Generate one sector-wide random factor per sector this tick
            sector_factors: dict[str, float] = {
                sector: self._rng.gauss(0, 1)
                for sector in SECTOR_CORRELATION
            }

            for ticker, state in list(self._tickers.items()):
                if self._rng.random() < EVENT_PROBABILITY:
                    self._apply_event(state)
                else:
                    corr = SECTOR_CORRELATION.get(state.sector, 0.0)
                    z_sector = sector_factors.get(state.sector, 0.0)
                    z_idio = self._rng.gauss(0, 1)
                    z = corr * z_sector + math.sqrt(max(0.0, 1 - corr**2)) * z_idio
                    self._step_price(state, dt, z)

                tick = PriceTick(
                    ticker=ticker,
                    price=state.price,
                    prev_close=state.prev_close,
                    timestamp=now,
                )
                if self._callback:
                    await self._callback(tick)
