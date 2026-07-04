"""Feature engineering.

Converts a :class:`MatchContext` into

1. a flat numeric feature vector consumed by the ML ensemble, and
2. adjusted goal expectations (lambda_home, lambda_away) produced by a
   transparent factor model, together with the list of
   :class:`FactorImpact` items that explain every adjustment.

The factor model works multiplicatively on baseline expectations derived from
team ratings, recent xG and venue splits, so the impact of each factor
(injuries, fatigue, weather, motivation, tactics, H2H, referee, travel) is
individually quantifiable and reportable to the user.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.schemas import AvailabilityStatus, FactorImpact, MatchContext


@dataclass
class EngineeredMatch:
    context: MatchContext
    lambda_home: float
    lambda_away: float
    features: dict[str, float]
    impacts: list[FactorImpact] = field(default_factory=list)
    headline_stats: dict[str, str] = field(default_factory=dict)


def _availability_penalty(ctx: MatchContext, team_side: str) -> tuple[float, list[FactorImpact]]:
    squad = ctx.home_squad if team_side == "home" else ctx.away_squad
    team = ctx.home_team if team_side == "home" else ctx.away_team
    impacts: list[FactorImpact] = []
    penalty = 0.0
    for item in squad.availability:
        if item.status in (AvailabilityStatus.INJURED, AvailabilityStatus.SUSPENDED):
            loss = item.player.importance * 0.055
            penalty += loss
            impacts.append(FactorImpact(
                factor=f"{team.short_name} missing {item.player.name} ({item.player.position})",
                direction="risk" if team_side == "home" else "favorable",
                impact=round(-loss if team_side == "home" else loss, 3),
                evidence=f"{item.status.value}: {item.detail}; player importance {item.player.importance:.0%}, "
                         f"avg rating {item.player.stats.avg_rating}",
            ))
        elif item.status == AvailabilityStatus.RETURNED:
            gain = item.player.importance * 0.02
            penalty -= gain
            impacts.append(FactorImpact(
                factor=f"{team.short_name}: {item.player.name} recovered",
                direction="favorable" if team_side == "home" else "risk",
                impact=round(gain if team_side == "home" else -gain, 3),
                evidence=item.detail,
            ))
    return min(penalty, 0.30), impacts


def engineer(ctx: MatchContext) -> EngineeredMatch:
    home, away = ctx.home_team, ctx.away_team
    f5h, f10h = ctx.home_form[5], ctx.home_form[10]
    f5a, f10a = ctx.away_form[5], ctx.away_form[10]
    vh, va = ctx.home_venue_split, ctx.away_venue_split
    impacts: list[FactorImpact] = []

    # ---------------------------------------------------------------- baseline
    # Blend of long-run ratings, venue-specific xG and recent per-game xG.
    xg_h_recent = (0.5 * f5h.xg_for / 5 + 0.5 * f10h.xg_for / 10)
    xg_a_recent = (0.5 * f5a.xg_for / 5 + 0.5 * f10a.xg_for / 10)
    xga_h_recent = (0.5 * f5h.xg_against / 5 + 0.5 * f10h.xg_against / 10)
    xga_a_recent = (0.5 * f5a.xg_against / 5 + 0.5 * f10a.xg_against / 10)

    rating_h = 1.30 * (home.attack_rating / 100) * (1.35 - away.defence_rating / 100) + 0.30
    rating_a = 1.25 * (away.attack_rating / 100) * (1.35 - home.defence_rating / 100)

    lam_h = 0.40 * rating_h + 0.30 * (xg_h_recent * 0.55 + xga_a_recent * 0.45) + 0.30 * vh.xg_for_avg
    lam_a = 0.40 * rating_a + 0.30 * (xg_a_recent * 0.55 + xga_h_recent * 0.45) + 0.30 * va.xg_for_avg

    impacts.append(FactorImpact(
        factor="Home advantage",
        direction="favorable", impact=0.05,
        evidence=f"{home.short_name} averages {vh.points_per_game:.2f} pts/game at home "
                 f"vs {va.points_per_game:.2f} for {away.short_name} away",
    ))

    # ------------------------------------------------------------------- form
    ppg_diff = f5h.points_per_game - f5a.points_per_game
    form_adj = max(-0.12, min(0.12, ppg_diff * 0.05))
    lam_h *= 1 + form_adj
    lam_a *= 1 - form_adj
    if abs(ppg_diff) > 0.4:
        better = home if ppg_diff > 0 else away
        worse = away if ppg_diff > 0 else home
        bf = f5h if ppg_diff > 0 else f5a
        wf = f5a if ppg_diff > 0 else f5h
        impacts.append(FactorImpact(
            factor=f"Form edge: {better.short_name}",
            direction="favorable" if ppg_diff > 0 else "risk",
            impact=round(form_adj, 3),
            evidence=f"Last 5: {better.short_name} {bf.wins}W-{bf.draws}D-{bf.losses}L "
                     f"({bf.points_per_game:.2f} ppg) vs {worse.short_name} "
                     f"{wf.wins}W-{wf.draws}D-{wf.losses}L ({wf.points_per_game:.2f} ppg)",
        ))

    # xG over/under-performance (regression-to-mean signal)
    finishing_h = (f10h.goals_for - f10h.xg_for) / 10
    finishing_a = (f10a.goals_for - f10a.xg_for) / 10
    lam_h *= 1 - max(-0.05, min(0.05, finishing_h * 0.10))
    lam_a *= 1 - max(-0.05, min(0.05, finishing_a * 0.10))
    if abs(finishing_h) > 0.25:
        impacts.append(FactorImpact(
            factor=f"{home.short_name} finishing vs xG",
            direction="risk" if finishing_h > 0 else "favorable",
            impact=round(-finishing_h * 0.05, 3),
            evidence=f"Scored {f10h.goals_for:.0f} from {f10h.xg_for:.1f} xG over last 10 — "
                     + ("over-performance likely to regress" if finishing_h > 0
                        else "under-performance suggests upside"),
        ))

    # -------------------------------------------------------- availability
    pen_h, imp_h = _availability_penalty(ctx, "home")
    pen_a, imp_a = _availability_penalty(ctx, "away")
    lam_h *= 1 - pen_h
    lam_a *= 1 - pen_a
    # missing defenders also help the opponent's attack
    lam_h *= 1 + pen_a * 0.45
    lam_a *= 1 + pen_h * 0.45
    impacts += imp_h + imp_a

    # -------------------------------------------------- fatigue & rotation
    for side, squad, team in (("home", ctx.home_squad, home), ("away", ctx.away_squad, away)):
        fatigue_adj = squad.fatigue_index * 0.08 + squad.rotation_risk * 0.06
        if side == "home":
            lam_h *= 1 - fatigue_adj
        else:
            lam_a *= 1 - fatigue_adj
        if squad.european_fixture_within_4d or squad.fatigue_index > 0.45:
            impacts.append(FactorImpact(
                factor=f"{team.short_name} fatigue / rotation",
                direction="risk" if side == "home" else "favorable",
                impact=round(-fatigue_adj if side == "home" else fatigue_adj, 3),
                evidence=f"fatigue index {squad.fatigue_index:.0%}, rotation risk "
                         f"{squad.rotation_risk:.0%}, {squad.days_rest} days rest"
                         + (", European fixture within 4 days" if squad.european_fixture_within_4d else ""),
            ))

    # ----------------------------------------------------------- motivation
    mot_gap = ctx.home_motivation.importance - ctx.away_motivation.importance
    lam_h *= 1 + max(-0.06, min(0.06, mot_gap * 0.08))
    lam_a *= 1 - max(-0.06, min(0.06, mot_gap * 0.08))
    if abs(mot_gap) > 0.2:
        motivated = home if mot_gap > 0 else away
        m = ctx.home_motivation if mot_gap > 0 else ctx.away_motivation
        o = ctx.away_motivation if mot_gap > 0 else ctx.home_motivation
        impacts.append(FactorImpact(
            factor=f"Motivation edge: {motivated.short_name}",
            direction="favorable" if mot_gap > 0 else "risk",
            impact=round(mot_gap * 0.08, 3),
            evidence=f"{motivated.short_name}: {', '.join(m.context)} (importance {m.importance:.0%}) "
                     f"vs opponent: {', '.join(o.context)} ({o.importance:.0%})",
        ))

    # -------------------------------------------------------------- tactics
    th, ta = ctx.home_tactics, ctx.away_tactics
    # high press vs team that struggles under pressure
    if th.pressing_intensity > 0.65 and "struggles under high press" in ta.weaknesses:
        lam_h *= 1.05
        impacts.append(FactorImpact(
            factor="Tactical matchup favours home press",
            direction="favorable", impact=0.05,
            evidence=f"{home.short_name} presses at {th.pressing_intensity:.0%} intensity; "
                     f"{away.short_name} listed weakness: struggles under high press",
        ))
    if ta.counter_attack_threat > 0.7 and th.defensive_line_height > 0.7:
        lam_a *= 1.06
        impacts.append(FactorImpact(
            factor=f"{away.short_name} counter-attack threat vs high line",
            direction="risk", impact=-0.06,
            evidence=f"{away.short_name} counter threat {ta.counter_attack_threat:.0%}; "
                     f"{home.short_name} defensive line height {th.defensive_line_height:.0%}",
        ))
    if th.set_piece_threat > 0.65 and ta.set_piece_weakness > 0.5:
        lam_h *= 1.04
        impacts.append(FactorImpact(
            factor=f"{home.short_name} set-piece edge",
            direction="favorable", impact=0.04,
            evidence=f"set-piece threat {th.set_piece_threat:.0%} vs opponent weakness "
                     f"{ta.set_piece_weakness:.0%}",
        ))

    # --------------------------------------------------------------- weather
    w = ctx.weather
    if w.condition in ("heavy_rain", "snow"):
        lam_h *= 0.94
        lam_a *= 0.94
        impacts.append(FactorImpact(
            factor=f"Weather: {w.condition.replace('_', ' ')}",
            direction="risk", impact=-0.06,
            evidence=f"{w.impact_note} ({w.temperature_c}°C, {w.precipitation_mm}mm, "
                     f"pitch: {w.pitch_condition})",
        ))
    elif w.wind_kmh > 30:
        lam_h *= 0.97
        lam_a *= 0.97
        impacts.append(FactorImpact(
            factor="Strong wind", direction="risk", impact=-0.03,
            evidence=f"wind {w.wind_kmh} km/h disturbs aerial play and crossing",
        ))

    # ---------------------------------------------------------------- travel
    if ctx.travel.away_travel_km > 1200:
        lam_a *= 0.975
        impacts.append(FactorImpact(
            factor="Away travel burden", direction="favorable", impact=0.025,
            evidence=f"{away.short_name} travels {ctx.travel.away_travel_km:.0f} km"
                     + (f", {ctx.travel.timezone_shift_h}h timezone shift" if ctx.travel.timezone_shift_h else ""),
        ))

    # ------------------------------------------------------------------- h2h
    h2h10 = ctx.h2h[10]
    if h2h10.played >= 6:
        h2h_edge = (h2h10.home_team_wins - h2h10.away_team_wins) / h2h10.played
        lam_h *= 1 + max(-0.03, min(0.03, h2h_edge * 0.05))
        if abs(h2h_edge) > 0.3:
            impacts.append(FactorImpact(
                factor="Head-to-head trend",
                direction="favorable" if h2h_edge > 0 else "risk",
                impact=round(h2h_edge * 0.05, 3),
                evidence=f"Last {h2h10.played} meetings: {h2h10.home_team_wins} home wins, "
                         f"{h2h10.draws} draws, {h2h10.away_team_wins} away wins; "
                         f"avg {h2h10.avg_goals:.2f} goals, BTTS {h2h10.btts_pct:.0%}",
            ))

    # -------------------------------------------------------------- referee
    ref = ctx.referee
    if ref.avg_yellow_cards > 4.5:
        impacts.append(FactorImpact(
            factor=f"Card-heavy referee: {ref.name}",
            direction="neutral", impact=0.0,
            evidence=f"{ref.avg_yellow_cards:.1f} yellows and {ref.penalties_per_match:.2f} "
                     f"penalties per match over {ref.matches} games — relevant for cards markets",
        ))

    lam_h = max(0.15, min(4.2, lam_h))
    lam_a = max(0.12, min(3.8, lam_a))

    # ------------------------------------------------------- feature vector
    features = {
        "elo_diff": home.elo - away.elo,
        "attack_diff": home.attack_rating - away.attack_rating,
        "defence_diff": home.defence_rating - away.defence_rating,
        "ppg5_diff": f5h.points_per_game - f5a.points_per_game,
        "ppg10_diff": f10h.points_per_game - f10a.points_per_game,
        "xg5_h": f5h.xg_for / 5, "xg5_a": f5a.xg_for / 5,
        "xga5_h": f5h.xg_against / 5, "xga5_a": f5a.xg_against / 5,
        "possession_diff": f10h.possession_pct - f10a.possession_pct,
        "ppda_diff": f10a.ppda - f10h.ppda,
        "big_chances_diff": f10h.big_chances_created - f10a.big_chances_created,
        "deep_completions_diff": f10h.deep_completions - f10a.deep_completions,
        "venue_ppg_diff": vh.points_per_game - va.points_per_game,
        "injury_pen_h": pen_h, "injury_pen_a": pen_a,
        "fatigue_h": ctx.home_squad.fatigue_index, "fatigue_a": ctx.away_squad.fatigue_index,
        "motivation_diff": mot_gap,
        "h2h_home_edge": (h2h10.home_team_wins - h2h10.away_team_wins) / max(1, h2h10.played),
        "weather_penalty": 1.0 if w.condition in ("heavy_rain", "snow") else 0.0,
        "lambda_home": lam_h, "lambda_away": lam_a,
    }

    headline = {
        "Last 5 (home)": f"{f5h.wins}W-{f5h.draws}D-{f5h.losses}L, xG {f5h.xg_for:.1f}/{f5h.xg_against:.1f}",
        "Last 5 (away)": f"{f5a.wins}W-{f5a.draws}D-{f5a.losses}L, xG {f5a.xg_for:.1f}/{f5a.xg_against:.1f}",
        "Venue split": f"{home.short_name} {vh.points_per_game:.2f} ppg home / {away.short_name} {va.points_per_game:.2f} ppg away",
        "H2H last 10": f"{h2h10.home_team_wins}-{h2h10.draws}-{h2h10.away_team_wins}, avg {h2h10.avg_goals:.2f} goals",
        "PPDA (pressing)": f"{f10h.ppda:.1f} vs {f10a.ppda:.1f} (lower = more press)",
        "Referee": f"{ref.name}: {ref.avg_yellow_cards:.1f} YC/match, {ref.penalties_per_match:.2f} pens",
        "Weather": f"{w.condition.replace('_', ' ')}, {w.temperature_c}°C, wind {w.wind_kmh} km/h",
        "Adjusted xG": f"{lam_h:.2f} - {lam_a:.2f}",
    }

    return EngineeredMatch(
        context=ctx, lambda_home=round(lam_h, 3), lambda_away=round(lam_a, 3),
        features=features, impacts=impacts, headline_stats=headline,
    )
