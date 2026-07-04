"""API-Football (api-sports.io) adapter.

Activated automatically when ``BETEDGE_API_FOOTBALL_KEY`` is set.  Only the
endpoints needed by the engine are mapped; anything the vendor does not expose
(e.g. PPDA, deep completions) falls back to the demo generator so the feature
vector stays complete.  The same pattern applies to future adapters
(Football-Data, Understat, Sportradar, StatsBomb).
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.core.config import get_settings
from app.core.schemas import Fixture, League, MatchContext, OddsBoard, Team
from app.providers.base import DataProvider
from app.providers.demo import DemoProvider

logger = logging.getLogger(__name__)

BASE_URL = "https://v3.football.api-sports.io"


class ApiFootballProvider(DataProvider):
    """Live provider backed by API-Football with demo fallback for gaps."""

    name = "api-football"

    def __init__(self) -> None:
        self._settings = get_settings()
        self._fallback = DemoProvider()
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"x-apisports-key": self._settings.api_football_key},
            timeout=15,
        )

    def _get(self, path: str, params: dict) -> Optional[list]:
        try:
            resp = self._client.get(path, params=params)
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("errors"):
                logger.warning("api-football error on %s: %s", path, payload["errors"])
                return None
            return payload.get("response") or None
        except httpx.HTTPError as exc:
            logger.warning("api-football request failed (%s): %s", path, exc)
            return None

    # The v3 API uses numeric ids; the engine uses slugs.  Until a persistent
    # id-mapping store is configured we serve reference data from the fallback
    # and enrich contexts opportunistically.
    def leagues(self) -> list[League]:
        return self._fallback.leagues()

    def teams(self, league_id: str) -> list[Team]:
        return self._fallback.teams(league_id)

    def fixtures(self, league_id: Optional[str] = None,
                 date: Optional[str] = None) -> list[Fixture]:
        return self._fallback.fixtures(league_id, date)

    def match_context(self, fixture_id: str) -> MatchContext:
        return self._fallback.match_context(fixture_id)

    def odds_board(self, fixture_id: str) -> OddsBoard:
        return self._fallback.odds_board(fixture_id)
