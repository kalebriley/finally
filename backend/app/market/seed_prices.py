"""Seed prices and GBM parameters for the market simulator."""

# Per-ticker seed prices and simulation parameters.
# price: starting price (also used as prev_close baseline)
# volatility: annualised volatility for GBM
# sector: used for correlated moves between related tickers
TICKER_SEEDS: dict[str, dict] = {
    "AAPL":  {"price": 190.00, "volatility": 0.25, "sector": "tech"},
    "GOOGL": {"price": 175.00, "volatility": 0.28, "sector": "tech"},
    "MSFT":  {"price": 420.00, "volatility": 0.22, "sector": "tech"},
    "AMZN":  {"price": 185.00, "volatility": 0.30, "sector": "tech"},
    "TSLA":  {"price": 250.00, "volatility": 0.55, "sector": "auto"},
    "NVDA":  {"price": 880.00, "volatility": 0.45, "sector": "tech"},
    "META":  {"price": 500.00, "volatility": 0.32, "sector": "tech"},
    "JPM":   {"price": 195.00, "volatility": 0.20, "sector": "finance"},
    "V":     {"price": 280.00, "volatility": 0.18, "sector": "finance"},
    "NFLX":  {"price": 620.00, "volatility": 0.35, "sector": "tech"},
}

# Fallback for tickers not in the seed table (e.g., AI trades an unknown ticker).
DEFAULT_SEED: dict = {"price": 100.00, "volatility": 0.30, "sector": "other"}

# GBM parameters
DRIFT: float = 0.0  # Zero drift — no systematic up/down bias over a session
TICK_INTERVAL: float = 0.5  # Seconds between simulator updates
SECONDS_PER_TRADING_YEAR: float = 252 * 6.5 * 3600  # ~5.9M seconds

# Intra-sector correlation: tickers in the same sector co-move with this weight.
# Z_ticker = corr * Z_sector + sqrt(1 - corr²) * Z_idiosyncratic
SECTOR_CORRELATION: dict[str, float] = {
    "tech":    0.6,
    "finance": 0.5,
    "auto":    0.3,
    "other":   0.0,  # Unknown sectors are fully uncorrelated
}

# Random event parameters: occasional sudden 2–5% moves for visual drama
EVENT_PROBABILITY: float = 0.002  # ~0.2% chance per tick per ticker
EVENT_MAGNITUDE_MIN: float = 0.02  # 2% minimum move
EVENT_MAGNITUDE_MAX: float = 0.05  # 5% maximum move
