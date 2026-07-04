"""REST API.

The `/analyze` endpoint is the core product: given a target odds value and an
optional league/fixture/date filter it scans every available fixture and
market and returns the pick with the highest estimated success probability
compatible with that price, fully motivated.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.core.schemas import AnalysisRequest, BetRecommendation
from app.markets.selector import analyse_fixture, rank_recommendations
from app.providers import get_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# In-memory prediction history (swap for a DB in production deployments).
_HISTORY: list[dict] = []
_MAX_HISTORY = 200


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "provider": get_provider().name,
            "time": datetime.now(timezone.utc).isoformat()}


@router.get("/leagues")
def leagues() -> list:
    return [l.model_dump() for l in get_provider().leagues()]


@router.get("/leagues/{league_id}/teams")
def teams(league_id: str) -> list:
    return [t.model_dump() for t in get_provider().teams(league_id)]


@router.get("/fixtures")
def fixtures(league_id: str | None = None, date: str | None = None,
             q: str | None = Query(None, description="search team name")) -> list:
    items = get_provider().fixtures(league_id, date)
    if q:
        needle = q.lower()
        provider = get_provider()
        team_names: dict[str, str] = {}
        for f in items:
            for tid in (f.home_team_id, f.away_team_id):
                if tid not in team_names:
                    team_names[tid] = ""
        for lid in {f.league_id for f in items}:
            for t in provider.teams(lid):
                if t.id in team_names:
                    team_names[t.id] = t.name.lower()
        items = [f for f in items
                 if needle in team_names.get(f.home_team_id, "")
                 or needle in team_names.get(f.away_team_id, "")]
    out = []
    provider = get_provider()
    league_names = {l.id: l.name for l in provider.leagues()}
    name_cache: dict[str, str] = {}
    for lid in {f.league_id for f in items}:
        for t in provider.teams(lid):
            name_cache[t.id] = t.name
    for f in items[:120]:
        d = f.model_dump()
        d["home_team"] = name_cache.get(f.home_team_id, f.home_team_id)
        d["away_team"] = name_cache.get(f.away_team_id, f.away_team_id)
        d["league"] = league_names.get(f.league_id, f.league_id)
        out.append(d)
    return out


@router.get("/fixtures/{fixture_id}/context")
def fixture_context(fixture_id: str) -> dict:
    try:
        return get_provider().match_context(fixture_id).model_dump()
    except KeyError:
        raise HTTPException(404, "fixture not found")


@router.get("/fixtures/{fixture_id}/odds")
def fixture_odds(fixture_id: str) -> dict:
    try:
        return get_provider().odds_board(fixture_id).model_dump()
    except KeyError:
        raise HTTPException(404, "fixture not found")


def _analyse_one(fixture_id: str, target: float,
                 strict: bool = True) -> BetRecommendation | None:
    provider = get_provider()
    ctx = provider.match_context(fixture_id)
    board = provider.odds_board(fixture_id)
    return analyse_fixture(ctx, board, target, strict_tolerance=strict)


@router.post("/analyze")
def analyze(req: AnalysisRequest) -> dict:
    provider = get_provider()

    if req.fixture_id:
        try:
            rec = _analyse_one(req.fixture_id, req.target_odds, strict=True)
            if rec is None:
                rec = _analyse_one(req.fixture_id, req.target_odds, strict=False)
        except KeyError:
            raise HTTPException(404, "fixture not found")
        if rec is None:
            raise HTTPException(422, "no market compatible with the requested odds "
                                     "was found for this fixture")
        recs = [rec]
    else:
        fixtures = provider.fixtures(req.league_id, req.date)
        if not fixtures:
            raise HTTPException(404, "no fixtures match the filters")
        recs = []
        for f in fixtures[:24]:  # scan cap keeps latency bounded
            try:
                rec = analyse_fixture(provider.match_context(f.id),
                                      provider.odds_board(f.id),
                                      req.target_odds)
                if rec:
                    recs.append(rec)
            except Exception:
                logger.exception("analysis failed for %s", f.id)
        if not recs:
            raise HTTPException(422, "no market compatible with the requested odds "
                                     "was found across the scanned fixtures")
        recs = rank_recommendations(recs)

    best = recs[0]
    entry = {
        "id": uuid.uuid4().hex[:10],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "match": best.match_label,
        "league": best.league,
        "kickoff_utc": best.kickoff_utc.isoformat(),
        "target_odds": req.target_odds,
        "market": best.pick.market,
        "selection": best.pick.selection,
        "odds": best.pick.offered_odds,
        "bookmaker": best.pick.bookmaker,
        "probability": best.pick.estimated_probability,
        "value_margin_pct": best.pick.value_margin_pct,
        "confidence": best.pick.confidence,
        "confidence_label": best.pick.confidence_label,
    }
    _HISTORY.insert(0, entry)
    del _HISTORY[_MAX_HISTORY:]

    return {
        "best": best.model_dump(),
        "other_matches": [
            {
                "fixture_id": r.fixture_id,
                "match": r.match_label,
                "league": r.league,
                "kickoff_utc": r.kickoff_utc.isoformat(),
                "market": r.pick.market,
                "selection": r.pick.selection,
                "odds": r.pick.offered_odds,
                "probability": r.pick.estimated_probability,
                "value_margin_pct": r.pick.value_margin_pct,
                "confidence": r.pick.confidence,
                "confidence_label": r.pick.confidence_label,
            }
            for r in recs[1:8]
        ],
    }


@router.get("/history")
def history() -> list[dict]:
    return _HISTORY


@router.get("/fixtures/{fixture_id}/live")
def live_refresh(fixture_id: str, target_odds: float = Query(2.0, gt=1.0)) -> dict:
    """Re-runs the full pipeline on the latest data (odds, lineups, weather).

    The frontend polls this endpoint so probabilities and picks stay current
    as the market and team news move.
    """
    try:
        rec = _analyse_one(fixture_id, target_odds, strict=False)
    except KeyError:
        raise HTTPException(404, "fixture not found")
    if rec is None:
        raise HTTPException(422, "no compatible market at this price")
    return rec.model_dump()
