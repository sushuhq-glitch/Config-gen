"""Application configuration.

All external data-provider credentials are read from environment variables so
that the platform can be pointed at real feeds (API-Football, Football-Data,
Understat, Sportradar, ...) without code changes.  When no credentials are
present the platform runs against the built-in demo provider, which produces
realistic, internally-consistent data for every league it models.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "BetEdge Pro"
    debug: bool = False

    # --- external data providers (optional) ---------------------------------
    api_football_key: str = ""
    football_data_key: str = ""
    odds_api_key: str = ""
    weather_api_key: str = ""

    # --- engine parameters ---------------------------------------------------
    simulation_runs: int = 100_000
    ml_training_samples: int = 12_000
    # Maximum |target - offered| relative distance for a market to be
    # considered compatible with the requested odds.
    odds_tolerance: float = 0.22
    # Minimum estimated probability for a pick to be surfaced at all.
    min_probability_floor: float = 0.02

    model_config = {"env_prefix": "BETEDGE_", "env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
