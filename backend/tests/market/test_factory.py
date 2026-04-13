"""Tests for the market data source factory."""

import os

from app.market.factory import create_market_data_source
from app.market.interface import MarketDataSource
from app.market.massive_client import MassiveMarketDataSource
from app.market.simulator import SimulatorMarketDataSource


def _create_with_key(key: str) -> MarketDataSource:
    old = os.environ.get("MASSIVE_API_KEY")
    os.environ["MASSIVE_API_KEY"] = key
    try:
        return create_market_data_source()
    finally:
        if old is None:
            os.environ.pop("MASSIVE_API_KEY", None)
        else:
            os.environ["MASSIVE_API_KEY"] = old


def _create_without_key() -> MarketDataSource:
    old = os.environ.pop("MASSIVE_API_KEY", None)
    try:
        return create_market_data_source()
    finally:
        if old is not None:
            os.environ["MASSIVE_API_KEY"] = old


# ---------------------------------------------------------------------------
# Simulator selection
# ---------------------------------------------------------------------------


def test_no_env_var_returns_simulator():
    source = _create_without_key()
    assert isinstance(source, SimulatorMarketDataSource)


def test_empty_api_key_returns_simulator():
    source = _create_with_key("")
    assert isinstance(source, SimulatorMarketDataSource)


def test_whitespace_api_key_returns_simulator():
    source = _create_with_key("   ")
    assert isinstance(source, SimulatorMarketDataSource)


# ---------------------------------------------------------------------------
# Massive selection
# ---------------------------------------------------------------------------


def test_valid_api_key_returns_massive():
    source = _create_with_key("test-api-key-123")
    assert isinstance(source, MassiveMarketDataSource)


def test_massive_source_has_correct_api_key():
    source = _create_with_key("my-key")
    assert isinstance(source, MassiveMarketDataSource)
    assert source._api_key == "my-key"


# ---------------------------------------------------------------------------
# Interface conformance
# ---------------------------------------------------------------------------


def test_simulator_implements_interface():
    source = _create_without_key()
    assert isinstance(source, MarketDataSource)


def test_massive_implements_interface():
    source = _create_with_key("any-key")
    assert isinstance(source, MarketDataSource)


# ---------------------------------------------------------------------------
# Each call returns a fresh instance
# ---------------------------------------------------------------------------


def test_returns_new_instance_each_call():
    s1 = _create_without_key()
    s2 = _create_without_key()
    assert s1 is not s2
