from functools import lru_cache

from app.core.config import get_settings
from app.providers.base import DataProvider
from app.providers.demo import DemoProvider


@lru_cache
def get_provider() -> DataProvider:
    settings = get_settings()
    if settings.api_football_key:
        from app.providers.api_football import ApiFootballProvider
        return ApiFootballProvider()
    return DemoProvider()
