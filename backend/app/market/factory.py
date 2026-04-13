"""Factory for creating the appropriate market data source.

Reads MASSIVE_API_KEY from the environment. If set and non-empty, creates
a MassiveMarketDataSource. Otherwise, creates a SimulatorMarketDataSource.

This is the only place where the choice of data source is made. All other
code depends on the MarketDataSource interface and is source-agnostic.
"""

import os

from .interface import MarketDataSource


def create_market_data_source() -> MarketDataSource:
    """Create the appropriate market data source based on environment config.

    Returns:
        SimulatorMarketDataSource if MASSIVE_API_KEY is unset or empty.
        MassiveMarketDataSource if MASSIVE_API_KEY is set and non-empty.
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        from .massive_client import MassiveMarketDataSource
        return MassiveMarketDataSource(api_key=api_key)

    from .simulator import SimulatorMarketDataSource
    return SimulatorMarketDataSource()
