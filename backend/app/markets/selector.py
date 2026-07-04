"""Best-bet selection.

Pipeline per fixture:

1. Feature engineering  ->  adjusted goal expectations + factor impacts
2. ML ensemble          ->  model probabilities for core markets
3. Monte Carlo          ->  probabilities for every listed market
4. Blend                ->  final probability per market
                            (simulation everywhere, ensemble blended in on
                            the markets it covers, weighted by agreement)
5. Filter by requested odds, rank by estimated probability (the primary
   objective) then value margin and confidence; emit a fully-motivated
   recommendation.

The ranking deliberately optimises probability-of-success at the requested
price point rather than raw expected value: that is the product requirement.
Value margin and CLV are still computed and reported so the user can see
whether the pick also beats the closing market.
"""
from __future__ import annotations

import hashlib
from typing import Optional

from app.analysis.features import EngineeredMatch, engineer
from app.core.config import get_settings
from app.core.schemas import (
    BetCandidate, BetRecommendation, FactorImpact, MarketSelection,
    MatchContext, ModelProbability, OddsBoard,
)
from app.ml.ensemble import MLEnsemble
from app.simulation.monte_carlo import SimulationResult, simulate

DISCLAIMER = (
    "Estimates are probabilistic, never certainties. Models are calibrated on "
    "historical patterns and cannot anticipate every event (red cards, "
    "individual errors, refereeing decisions). Bet responsibly and only what "
    "you can afford to lose. 18+."
)

ENSEMBLE_MARKETS = {"1x2_home", "1x2_draw", "1x2_away", "ou_2.5_over", "btts_yes"}
DERIVED_FROM_ENSEMBLE = {
    "ou_2.5_under": ("ou_2.5_over", True),
    "btts_no": ("btts_yes", True),
}


def _confidence_label(score: float) -> str:
    if score >= 80:
        return "Very High"
    if score >= 65:
        return "High"
    if score >= 50:
        return "Medium"
    return "Low"


def blended_probabilities(sim: SimulationResult,
                          ensemble_probs: dict[str, float],
                          agreement: float) -> dict[str, float]:
    """Blend simulation and ML ensemble; the more the models agree, the more
    weight the ensemble gets (up to 50/50)."""
    w_ml = 0.25 + 0.25 * agreement
    probs = dict(sim.market_probs)
    for key in ENSEMBLE_MARKETS:
        if key in probs and key in ensemble_probs:
            probs[key] = (1 - w_ml) * probs[key] + w_ml * ensemble_probs[key]
    for key, (src, complement) in DERIVED_FROM_ENSEMBLE.items():
        if key in probs and src in ensemble_probs:
            blended_src = probs[src]
            probs[key] = 1 - blended_src if complement else blended_src
    # keep 1x2 a proper distribution
    s = probs["1x2_home"] + probs["1x2_draw"] + probs["1x2_away"]
    for k in ("1x2_home", "1x2_draw", "1x2_away"):
        probs[k] /= s
    probs["dc_1x"] = probs["1x2_home"] + probs["1x2_draw"]
    probs["dc_12"] = probs["1x2_home"] + probs["1x2_away"]
    probs["dc_x2"] = probs["1x2_draw"] + probs["1x2_away"]
    nd = probs["1x2_home"] + probs["1x2_away"]
    probs["dnb_home"] = probs["1x2_home"] / nd if nd else 0.5
    probs["dnb_away"] = 1 - probs["dnb_home"]
    return probs


def _candidate(sel: MarketSelection, prob: float, target: float,
               agreement: float, data_quality: float) -> BetCandidate:
    value_margin = (prob * sel.best_odds - 1) * 100
    fair = 1 / prob if prob > 0 else 999
    distance = abs(sel.best_odds - target) / target

    # Composite confidence: probability level, model agreement, value sanity,
    # market liquidity proxy (movement stability), data quality.
    conf = (
        40 * prob
        + 22 * agreement
        + 18 * data_quality
        + 12 * max(0.0, min(1.0, 0.5 + value_margin / 20))
        + 8 * (0.0 if sel.suspicious_movement else 1.0)
    )
    conf = max(5.0, min(97.0, conf))

    b = sel.best_odds - 1
    kelly = max(0.0, (prob * b - (1 - prob)) / b) if b > 0 else 0.0

    return BetCandidate(
        market=sel.market, selection=sel.selection, market_key=sel.market_key,
        offered_odds=sel.best_odds, bookmaker=sel.best_bookmaker,
        estimated_probability=round(prob, 4),
        fair_odds=round(fair, 2),
        value_margin_pct=round(value_margin, 2),
        confidence=round(conf, 1),
        confidence_label=_confidence_label(conf),
        odds_distance=round(distance, 4),
        kelly_fraction=round(min(kelly, 0.25), 4),
        model_agreement=round(agreement, 3),
    )


def _data_quality(ctx: MatchContext) -> float:
    """Proxy for how complete/trustworthy the context is."""
    q = 0.75
    if ctx.home_squad.lineup_confirmed and ctx.away_squad.lineup_confirmed:
        q += 0.15
    if ctx.h2h[10].played >= 8:
        q += 0.05
    if ctx.weather.condition in ("heavy_rain", "snow", "fog"):
        q -= 0.05
    return max(0.3, min(1.0, q))


def _reasoning(eng: EngineeredMatch, pick: BetCandidate,
               sim: SimulationResult, agreement: float,
               target: float) -> list[str]:
    ctx = eng.context
    home, away = ctx.home_team, ctx.away_team
    s = sim.summary
    lines = [
        f"Requested odds {target:.2f}: '{pick.selection}' ({pick.market}) at "
        f"{pick.offered_odds:.2f} ({pick.bookmaker}) is the compatible market with the "
        f"highest estimated success probability: {pick.estimated_probability:.1%}.",
        f"Across {s.runs:,} Monte Carlo simulations with adjusted expectations "
        f"xG {s.home_expected_goals:.2f}-{s.away_expected_goals:.2f}: "
        f"home win {s.home_win:.1%}, draw {s.draw:.1%}, away win {s.away_win:.1%}; "
        f"over 2.5 {s.over_25:.1%}, BTTS {s.btts:.1%}; average {s.avg_goals:.2f} goals.",
        f"The ML ensemble (Random Forest, Gradient Boosting, XGBoost, LightGBM, "
        f"neural network, Bayesian Dixon-Coles) shows {agreement:.0%} agreement "
        f"across models on this fixture.",
    ]
    if pick.value_margin_pct > 0:
        lines.append(
            f"The price carries positive expected value: fair odds {pick.fair_odds:.2f} "
            f"vs offered {pick.offered_odds:.2f} (+{pick.value_margin_pct:.1f}% margin).")
    else:
        lines.append(
            f"Note: the offered price is below fair odds ({pick.fair_odds:.2f}); the pick "
            f"maximises hit probability at your requested odds, not expected value "
            f"({pick.value_margin_pct:.1f}% margin).")
    top_pos = [i for i in eng.impacts if i.direction == "favorable"][:2]
    if top_pos:
        lines.append("Key drivers: " + "; ".join(
            f"{i.factor} ({i.evidence})" for i in top_pos) + ".")
    h2h = ctx.h2h[10]
    lines.append(
        f"H2H last {h2h.played}: {h2h.home_team_wins}-{h2h.draws}-{h2h.away_team_wins} "
        f"({home.short_name} first), avg {h2h.avg_goals:.2f} goals, BTTS {h2h.btts_pct:.0%}.")
    return lines


def analyse_fixture(ctx: MatchContext, board: OddsBoard,
                    target_odds: float,
                    strict_tolerance: bool = True) -> Optional[BetRecommendation]:
    settings = get_settings()
    eng = engineer(ctx)
    seed = int(hashlib.sha256(ctx.fixture.id.encode()).hexdigest()[:8], 16)
    sim = simulate(eng.lambda_home, eng.lambda_away, ctx, seed=seed)

    ensemble = MLEnsemble.instance()
    outputs = ensemble.predict(eng.features)
    ensemble_probs, agreement = MLEnsemble.combine(outputs)
    probs = blended_probabilities(sim, ensemble_probs, agreement)
    dq = _data_quality(ctx)

    tolerance = settings.odds_tolerance if strict_tolerance else settings.odds_tolerance * 2
    candidates: list[BetCandidate] = []
    for sel in board.selections:
        prob = probs.get(sel.market_key)
        if prob is None or prob < settings.min_probability_floor:
            continue
        if abs(sel.best_odds - target_odds) / target_odds > tolerance:
            continue
        candidates.append(_candidate(sel, prob, target_odds, agreement, dq))

    if not candidates:
        return None

    # Primary objective: highest probability of success. Distance to the
    # requested price and value margin act as soft tie-breakers.
    def rank_key(c: BetCandidate) -> float:
        return (c.estimated_probability
                - 0.08 * c.odds_distance
                + 0.0008 * max(-10, min(10, c.value_margin_pct)))

    candidates.sort(key=rank_key, reverse=True)
    pick, alternatives = candidates[0], candidates[1:6]

    favorable = sorted([i for i in eng.impacts if i.direction == "favorable"],
                       key=lambda i: -abs(i.impact))[:6]
    risks = sorted([i for i in eng.impacts if i.direction == "risk"],
                   key=lambda i: -abs(i.impact))[:6]
    if pick.model_agreement < 0.5:
        risks.append(FactorImpact(
            factor="Model disagreement", direction="risk", impact=-0.05,
            evidence="the prediction models diverge noticeably on this fixture; "
                     "treat the estimate with extra caution"))
    if not ctx.home_squad.lineup_confirmed:
        risks.append(FactorImpact(
            factor="Lineups not yet official", direction="risk", impact=-0.02,
            evidence="probabilities will be recalculated automatically when "
                     "official lineups are released (~1h before kickoff)"))

    model_breakdown = [
        ModelProbability(
            model=o.name, weight=o.weight,
            probabilities={
                "1x2_home": round(o.p_home, 4), "1x2_draw": round(o.p_draw, 4),
                "1x2_away": round(o.p_away, 4), "ou_2.5_over": round(o.p_over25, 4),
                "btts_yes": round(o.p_btts, 4),
            })
        for o in outputs
    ]

    return BetRecommendation(
        fixture_id=ctx.fixture.id,
        match_label=f"{ctx.home_team.name} vs {ctx.away_team.name}",
        kickoff_utc=ctx.fixture.kickoff_utc,
        league=ctx.league.name,
        target_odds=target_odds,
        pick=pick,
        alternatives=alternatives,
        reasoning=_reasoning(eng, pick, sim, agreement, target_odds),
        favorable_factors=favorable,
        risk_factors=risks,
        simulation=sim.summary,
        model_breakdown=model_breakdown,
        stats_used=eng.headline_stats,
        disclaimer=DISCLAIMER,
    )


def rank_recommendations(recs: list[BetRecommendation]) -> list[BetRecommendation]:
    return sorted(
        recs,
        key=lambda r: (r.pick.estimated_probability - 0.08 * r.pick.odds_distance),
        reverse=True,
    )
