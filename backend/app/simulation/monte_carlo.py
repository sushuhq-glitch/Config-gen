"""Monte Carlo match simulator.

Simulates ``settings.simulation_runs`` (default 100,000) virtual matches per
fixture using a bivariate Poisson process with a shared covariance component
(matches where both teams' scoring rates rise together, e.g. open games), plus
correlated corner and card processes.  Returns probabilities for every market
the odds board carries, along with the exact-score distribution.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.core.config import get_settings
from app.core.schemas import MatchContext, SimulationSummary


@dataclass
class SimulationResult:
    summary: SimulationSummary
    market_probs: dict[str, float] = field(default_factory=dict)


def simulate(lam_h: float, lam_a: float, ctx: MatchContext,
             runs: int | None = None, seed: int = 20240) -> SimulationResult:
    settings = get_settings()
    n = runs or settings.simulation_runs
    rng = np.random.default_rng(seed)

    # Shared component induces positive goal correlation (open vs closed games)
    shared = min(0.18, 0.1 * min(lam_h, lam_a))
    g_common = rng.poisson(shared, n)
    goals_h = rng.poisson(max(0.05, lam_h - shared), n) + g_common
    goals_a = rng.poisson(max(0.05, lam_a - shared), n) + g_common
    total = goals_h + goals_a

    # Corners scale with attacking volume; cards with referee profile + stakes
    f10h, f10a = ctx.home_form[10], ctx.away_form[10]
    corners_mu = np.clip((f10h.corners_for + f10a.corners_for) * 0.9
                         + (total - (lam_h + lam_a)) * 0.35, 4, 18)
    corners = rng.poisson(corners_mu)

    ref = ctx.referee
    stakes = (ctx.home_motivation.importance + ctx.away_motivation.importance) / 2
    cards_mu = np.clip(ref.avg_yellow_cards * (0.85 + stakes * 0.35)
                       + (f10h.cards_for + f10a.cards_for) * 0.25, 1.5, 10)
    cards = rng.poisson(cards_mu, n)

    p = {}
    p["1x2_home"] = float(np.mean(goals_h > goals_a))
    p["1x2_draw"] = float(np.mean(goals_h == goals_a))
    p["1x2_away"] = float(np.mean(goals_h < goals_a))
    p["dc_1x"] = p["1x2_home"] + p["1x2_draw"]
    p["dc_12"] = p["1x2_home"] + p["1x2_away"]
    p["dc_x2"] = p["1x2_draw"] + p["1x2_away"]
    for line in (1.5, 2.5, 3.5):
        p[f"ou_{line}_over"] = float(np.mean(total > line))
        p[f"ou_{line}_under"] = 1 - p[f"ou_{line}_over"]
    p["btts_yes"] = float(np.mean((goals_h > 0) & (goals_a > 0)))
    p["btts_no"] = 1 - p["btts_yes"]
    non_draw = p["1x2_home"] + p["1x2_away"]
    p["dnb_home"] = p["1x2_home"] / non_draw if non_draw else 0.5
    p["dnb_away"] = 1 - p["dnb_home"]
    p["ts_home"] = float(np.mean(goals_h > 0))
    p["ts_away"] = float(np.mean(goals_a > 0))
    p["ah_home_-1.5"] = float(np.mean(goals_h - goals_a >= 2))
    p["ah_away_+1.5"] = float(np.mean(goals_a - goals_h >= -1))
    p["corners_over_9.5"] = float(np.mean(corners > 9.5))
    p["corners_under_9.5"] = 1 - p["corners_over_9.5"]
    p["cards_over_4.5"] = float(np.mean(cards > 4.5))
    p["cards_under_4.5"] = 1 - p["cards_over_4.5"]

    # exact scores (top 6)
    capped_h = np.minimum(goals_h, 5)
    capped_a = np.minimum(goals_a, 5)
    combo = capped_h * 6 + capped_a
    counts = np.bincount(combo, minlength=36) / n
    order = np.argsort(counts)[::-1][:6]
    top_scores = [(f"{int(c // 6)}-{int(c % 6)}", round(float(counts[c]), 4))
                  for c in order]

    summary = SimulationSummary(
        runs=n,
        home_win=round(p["1x2_home"], 4),
        draw=round(p["1x2_draw"], 4),
        away_win=round(p["1x2_away"], 4),
        over_15=round(p["ou_1.5_over"], 4),
        over_25=round(p["ou_2.5_over"], 4),
        over_35=round(p["ou_3.5_over"], 4),
        under_25=round(p["ou_2.5_under"], 4),
        btts=round(p["btts_yes"], 4),
        avg_goals=round(float(total.mean()), 3),
        avg_corners=round(float(corners.mean()), 2),
        avg_cards=round(float(cards.mean()), 2),
        top_correct_scores=top_scores,
        home_expected_goals=round(lam_h, 2),
        away_expected_goals=round(lam_a, 2),
    )
    return SimulationResult(summary=summary, market_probs=p)
