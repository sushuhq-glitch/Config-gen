"""Abstract data-provider interface.

Every source of truth (API-Football, Football-Data, Understat, Sportradar,
StatsBomb, the built-in demo generator, ...) implements this interface so the
analysis engine never depends on a specific vendor.  A cross-validation layer
can wrap several providers and reconcile disagreements between them.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.core.schemas import Fixture, League, MatchContext, OddsBoard, Team


class DataProvider(ABC):
    name: str = "base"

    @abstractmethod
    def leagues(self) -> list[League]: ...

    @abstractmethod
    def teams(self, league_id: str) -> list[Team]: ...

    @abstractmethod
    def fixtures(
        self,
        league_id: Optional[str] = None,
        date: Optional[str] = None,
    ) -> list[Fixture]: ...

    @abstractmethod
    def match_context(self, fixture_id: str) -> MatchContext: ...

    @abstractmethod
    def odds_board(self, fixture_id: str) -> OddsBoard: ...
