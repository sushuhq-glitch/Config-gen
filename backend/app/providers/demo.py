"""Deterministic demo data provider.

Generates a full, internally-consistent dataset (fixtures, form, squads,
tactics, head-to-head, referees, weather, multi-bookmaker odds) for six
leagues.  Every value is derived from a seeded RNG keyed on the entity id, so
repeated calls return identical data — which makes the whole engine, the API
and the UI fully testable without external credentials.

The generated odds embed a realistic bookmaker margin (2-7%) around the
"true" probabilities implied by team ratings, so value-bet detection, CLV and
line-movement logic behave like they would against a live odds feed.
"""
from __future__ import annotations

import hashlib
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.schemas import (
    AvailabilityItem, AvailabilityStatus, BookmakerOdds, Fixture, FormWindow,
    H2HSummary, League, MarketSelection, MatchContext, MotivationFactor,
    OddsBoard, Player, PlayerStats, RefereeProfile, SquadReport, TacticalProfile,
    Team, TravelReport, VenueSplit, WeatherReport,
)
from app.providers import demo_data as D
from app.providers.base import DataProvider


def _rng(*parts: object) -> random.Random:
    seed = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return random.Random(int(seed[:16], 16))


def _poisson_pmf(lam: float, k: int) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


class DemoProvider(DataProvider):
    name = "demo"

    # ------------------------------------------------------------------ refs
    def leagues(self) -> list[League]:
        return [League(**l) for l in D.LEAGUES]

    def teams(self, league_id: str) -> list[Team]:
        rows = D.TEAMS.get(league_id, [])
        return [
            Team(
                id=f"{league_id}:{short.lower()}",
                name=name, short_name=short, league_id=league_id,
                attack_rating=atk, defence_rating=dfn, elo=elo,
            )
            for name, short, atk, dfn, elo in rows
        ]

    def _team(self, team_id: str) -> Team:
        league_id = team_id.split(":")[0]
        for t in self.teams(league_id):
            if t.id == team_id:
                return t
        raise KeyError(team_id)

    # -------------------------------------------------------------- fixtures
    def fixtures(self, league_id: Optional[str] = None,
                 date: Optional[str] = None) -> list[Fixture]:
        league_ids = [league_id] if league_id else [l["id"] for l in D.LEAGUES]
        out: list[Fixture] = []
        now = datetime.now(timezone.utc)
        for lid in league_ids:
            teams = self.teams(lid)
            if len(teams) < 2:
                continue
            # One "matchday" per upcoming day, deterministic pairing that
            # rotates with the ISO date so the schedule changes daily.
            for day in range(7):
                d = (now + timedelta(days=day)).date()
                r = _rng("fixtures", lid, d.isoformat())
                order = teams[:]
                r.shuffle(order)
                for i in range(0, len(order) - 1, 2):
                    home, away = order[i], order[i + 1]
                    hour = r.choice([13, 16, 19, 21])
                    kickoff = datetime(d.year, d.month, d.day, hour, 0,
                                       tzinfo=timezone.utc)
                    fid = f"{lid}~{home.short_name}~{away.short_name}~{d.isoformat()}"
                    out.append(Fixture(
                        id=fid, league_id=lid,
                        home_team_id=home.id, away_team_id=away.id,
                        kickoff_utc=kickoff,
                        venue=f"{home.name} Stadium",
                        round=f"Matchday {d.isocalendar().week}",
                    ))
        if date:
            out = [f for f in out if f.kickoff_utc.date().isoformat() == date]
        out.sort(key=lambda f: f.kickoff_utc)
        return out

    def _fixture(self, fixture_id: str) -> Fixture:
        lid, home_short, away_short, date = fixture_id.split("~")
        for f in self.fixtures(lid, date):
            if f.id == fixture_id:
                return f
        raise KeyError(fixture_id)

    # ------------------------------------------------------------- context
    def match_context(self, fixture_id: str) -> MatchContext:
        fx = self._fixture(fixture_id)
        league = next(League(**l) for l in D.LEAGUES if l["id"] == fx.league_id)
        home, away = self._team(fx.home_team_id), self._team(fx.away_team_id)

        return MatchContext(
            fixture=fx, league=league, home_team=home, away_team=away,
            home_form={w: self._form(home, w) for w in (5, 10, 20)},
            away_form={w: self._form(away, w) for w in (5, 10, 20)},
            home_venue_split=self._venue_split(home, home=True),
            away_venue_split=self._venue_split(away, home=False),
            home_squad=self._squad(home, fx),
            away_squad=self._squad(away, fx),
            home_tactics=self._tactics(home),
            away_tactics=self._tactics(away),
            h2h={w: self._h2h(home, away, w) for w in (5, 10, 20)},
            home_motivation=self._motivation(home, fx),
            away_motivation=self._motivation(away, fx),
            referee=self._referee(fx),
            weather=self._weather(fx),
            travel=self._travel(home, away, fx),
            attendance_expected=_rng("att", fx.id).randint(18_000, 74_000),
        )

    # -- team form ---------------------------------------------------------
    def _form(self, team: Team, window: int) -> FormWindow:
        r = _rng("form", team.id, window)
        # strength in [0,1]; drives every aggregate coherently
        s = (team.attack_rating + team.defence_rating) / 200
        atk = team.attack_rating / 100
        dfn = team.defence_rating / 100

        win_p = min(0.78, max(0.12, s * 0.95 + r.uniform(-0.08, 0.08)))
        draw_p = 0.24 + r.uniform(-0.05, 0.05)
        wins = round(window * win_p)
        draws = min(window - wins, round(window * draw_p))
        losses = window - wins - draws

        gf = window * (0.75 + atk * 1.5 + r.uniform(-0.15, 0.15))
        ga = window * (2.15 - dfn * 1.5 + r.uniform(-0.15, 0.15))
        return FormWindow(
            matches=window, wins=wins, draws=draws, losses=losses,
            goals_for=round(gf, 1), goals_against=round(ga, 1),
            xg_for=round(gf * r.uniform(0.9, 1.12), 1),
            xg_against=round(ga * r.uniform(0.9, 1.12), 1),
            shots=round(9 + atk * 9 + r.uniform(-1, 1), 1),
            shots_on_target=round(3 + atk * 4.5 + r.uniform(-0.5, 0.5), 1),
            big_chances_created=round(1.0 + atk * 2.4 + r.uniform(-0.3, 0.3), 1),
            big_chances_conceded=round(3.2 - dfn * 2.1 + r.uniform(-0.3, 0.3), 1),
            possession_pct=round(41 + s * 22 + r.uniform(-3, 3), 1),
            pass_accuracy_pct=round(76 + s * 14 + r.uniform(-2, 2), 1),
            ppda=round(14.5 - s * 6 + r.uniform(-1, 1), 1),
            recoveries=round(38 + s * 12 + r.uniform(-3, 3), 1),
            corners_for=round(3.6 + atk * 3.4 + r.uniform(-0.4, 0.4), 1),
            corners_against=round(7.4 - dfn * 3.4 + r.uniform(-0.4, 0.4), 1),
            cards_for=round(1.4 + (1 - dfn) * 1.4 + r.uniform(-0.2, 0.2), 1),
            cards_against=round(1.5 + atk * 0.8 + r.uniform(-0.2, 0.2), 1),
            deep_completions=round(4 + atk * 8 + r.uniform(-1, 1), 1),
            passes_final_third=round(28 + s * 34 + r.uniform(-3, 3), 1),
            dangerous_attacks=round(28 + atk * 30 + r.uniform(-3, 3), 1),
            points_per_game=round((wins * 3 + draws) / window, 2),
        )

    def _venue_split(self, team: Team, home: bool) -> VenueSplit:
        r = _rng("venue", team.id, home)
        s = (team.attack_rating + team.defence_rating) / 200
        boost = 0.12 if home else -0.10
        ppg = max(0.4, min(2.7, s * 2.6 + boost + r.uniform(-0.15, 0.15)))
        return VenueSplit(
            matches=12,
            points_per_game=round(ppg, 2),
            goals_for_avg=round(0.8 + s * 1.4 + (0.25 if home else -0.15) + r.uniform(-0.1, 0.1), 2),
            goals_against_avg=round(2.0 - s * 1.2 + (0.15 if not home else -0.1) + r.uniform(-0.1, 0.1), 2),
            xg_for_avg=round(0.9 + s * 1.3 + (0.2 if home else -0.1), 2),
            xg_against_avg=round(1.9 - s * 1.1 + (0.1 if not home else -0.1), 2),
            win_pct=round(min(0.85, max(0.1, s * 0.9 + boost)), 2),
            clean_sheet_pct=round(min(0.7, max(0.05, s * 0.55 + (0.06 if home else -0.04))), 2),
            btts_pct=round(0.62 - s * 0.18 + r.uniform(-0.05, 0.05), 2),
            over25_pct=round(0.42 + s * 0.22 + r.uniform(-0.05, 0.05), 2),
        )

    # -- squads --------------------------------------------------------------
    def _players(self, team: Team) -> list[Player]:
        r = _rng("players", team.id)
        positions = ["GK"] + ["DF"] * 5 + ["MF"] * 5 + ["FW"] * 4
        players: list[Player] = []
        s = (team.attack_rating + team.defence_rating) / 200
        for i, pos in enumerate(positions):
            name = f"{r.choice(D.FIRST_NAMES)} {r.choice(D.LAST_NAMES)}"
            base = s + r.uniform(-0.15, 0.15)
            fw = pos == "FW"
            mf = pos == "MF"
            players.append(Player(
                id=f"{team.id}:p{i}", name=name, team_id=team.id, position=pos,
                importance=round(min(1.0, max(0.05, base * (1.1 if fw else 0.9))), 2),
                stats=PlayerStats(
                    goals=r.randint(6, 18) if fw else r.randint(1, 7) if mf else r.randint(0, 2),
                    assists=r.randint(2, 10) if (fw or mf) else r.randint(0, 3),
                    xg=round(r.uniform(4, 14) if fw else r.uniform(0.5, 5), 1),
                    xa=round(r.uniform(1, 8) if (fw or mf) else r.uniform(0, 2), 1),
                    pass_accuracy_pct=round(74 + base * 18, 1),
                    shot_accuracy_pct=round(30 + base * 25, 1),
                    tackles_won_pct=round(48 + base * 22, 1),
                    dribbles_success_pct=round(40 + base * 25, 1),
                    fouls_per90=round(r.uniform(0.5, 2.2), 1),
                    yellow_cards=r.randint(1, 9),
                    red_cards=r.randint(0, 1),
                    avg_rating=round(6.2 + base * 1.3 + r.uniform(-0.2, 0.2), 2),
                    minutes_last_30d=r.randint(120, 450),
                    form_trend=r.choice(["improving", "stable", "stable", "declining"]),
                ),
            ))
        return players

    def _squad(self, team: Team, fx: Fixture) -> SquadReport:
        r = _rng("squad", team.id, fx.id)
        players = self._players(team)
        availability: list[AvailabilityItem] = []
        pool = players[:]
        r.shuffle(pool)
        n_inj = r.randint(0, 3)
        for p in pool[:n_inj]:
            availability.append(AvailabilityItem(
                player=p, status=AvailabilityStatus.INJURED,
                detail=r.choice(["hamstring strain", "ankle sprain", "muscle fatigue", "knee problem"]),
                expected_return=f"{r.randint(1, 5)} weeks",
            ))
        if r.random() < 0.25:
            availability.append(AvailabilityItem(
                player=pool[n_inj], status=AvailabilityStatus.SUSPENDED,
                detail="accumulated yellow cards"))
        for p in pool[n_inj + 1: n_inj + 3]:
            if r.random() < 0.4:
                availability.append(AvailabilityItem(
                    player=p, status=AvailabilityStatus.YELLOW_CARD_RISK,
                    detail="one booking from suspension"))
        if r.random() < 0.3:
            availability.append(AvailabilityItem(
                player=pool[-1], status=AvailabilityStatus.RETURNED,
                detail="passed late fitness test"))

        unavailable = {a.player.id for a in availability
                       if a.status in (AvailabilityStatus.INJURED, AvailabilityStatus.SUSPENDED)}
        lineup = [p for p in players if p.id not in unavailable][:11]
        in_form = [p.name for p in players if p.stats.form_trend == "improving"][:3]
        out_form = [p.name for p in players if p.stats.form_trend == "declining"][:3]

        european = fx.league_id != "champions-league" and r.random() < 0.25
        return SquadReport(
            team_id=team.id,
            availability=availability,
            probable_lineup=[p.name for p in lineup],
            lineup_confirmed=False,
            formation=r.choice(D.FORMATIONS),
            rotation_risk=round(r.uniform(0.05, 0.5) if european else r.uniform(0.02, 0.2), 2),
            fatigue_index=round(r.uniform(0.25, 0.6) if european else r.uniform(0.1, 0.35), 2),
            days_rest=r.choice([3, 4, 6, 7]) if european else r.choice([6, 7, 8]),
            european_fixture_within_4d=european,
            key_players_in_form=in_form,
            key_players_out_of_form=out_form,
        )

    def _tactics(self, team: Team) -> TacticalProfile:
        r = _rng("tactics", team.id)
        s = (team.attack_rating + team.defence_rating) / 200
        style = r.choice(D.STYLES if s < 0.75 else ["possession", "high-press", "balanced"])
        strengths_pool = [
            "clinical finishing in the box", "dominant in midfield duels",
            "dangerous from set pieces", "quick vertical transitions",
            "compact defensive block", "sustained high press wins the ball high",
            "width and crossing volume", "strong aerially on both boxes",
        ]
        weaknesses_pool = [
            "vulnerable to counter-attacks", "concedes from set pieces",
            "slow defensive line against pace", "struggles under high press",
            "over-reliant on key striker", "poor away from home",
            "loses control after 70'", "full-backs leave space behind",
        ]
        r.shuffle(strengths_pool)
        r.shuffle(weaknesses_pool)
        return TacticalProfile(
            team_id=team.id,
            formation=r.choice(D.FORMATIONS),
            probable_formation=r.choice(D.FORMATIONS),
            style=style,
            pressing_intensity=round(min(1, max(0, s + r.uniform(-0.2, 0.2))), 2),
            defensive_line_height=round(min(1, max(0, s + r.uniform(-0.25, 0.15))), 2),
            counter_attack_threat=round(r.uniform(0.3, 0.9), 2),
            crossing_volume=round(r.uniform(0.2, 0.85), 2),
            set_piece_threat=round(r.uniform(0.25, 0.85), 2),
            set_piece_weakness=round(r.uniform(0.15, 0.7), 2),
            strengths=strengths_pool[:3],
            weaknesses=weaknesses_pool[:2],
        )

    def _h2h(self, home: Team, away: Team, window: int) -> H2HSummary:
        key = "|".join(sorted([home.id, away.id]))
        r = _rng("h2h", key, window)
        sh = (home.attack_rating + home.defence_rating)
        sa = (away.attack_rating + away.defence_rating)
        edge = (sh - sa) / 400  # [-0.5, 0.5]
        hw_p = 0.40 + edge + r.uniform(-0.05, 0.05)
        aw_p = 0.32 - edge + r.uniform(-0.05, 0.05)
        hw = max(0, round(window * hw_p))
        aw = max(0, min(window - hw, round(window * aw_p)))
        dr = window - hw - aw
        avg_goals = round(r.uniform(2.1, 3.3), 2)
        over = round(min(0.9, max(0.1, (avg_goals - 1.6) / 2.2 + r.uniform(-0.06, 0.06))), 2)
        return H2HSummary(
            window=window, played=window,
            home_team_wins=hw, draws=dr, away_team_wins=aw,
            avg_goals=avg_goals, over25_pct=over,
            under25_pct=round(1 - over, 2),
            btts_pct=round(min(0.85, max(0.2, over + r.uniform(-0.12, 0.12))), 2),
            notes=[f"{home.short_name} unbeaten in {r.randint(1, min(4, window))} of the last {window} meetings at home"]
            if hw >= aw else
            [f"{away.short_name} has won {aw} of the last {window} meetings"],
        )

    def _motivation(self, team: Team, fx: Fixture) -> MotivationFactor:
        r = _rng("motivation", team.id, fx.id)
        ctx, importance = r.choice(D.MOTIVATION_CONTEXTS)
        extra = []
        if fx.league_id == "champions-league":
            ctx, importance = "european knockout stakes", 0.9
        if r.random() < 0.12:
            extra.append("local rivalry adds intensity")
            importance = min(1.0, importance + 0.1)
        return MotivationFactor(
            team_id=team.id, context=[ctx, *extra],
            importance=round(importance + r.uniform(-0.05, 0.05), 2),
            turnover_expected=r.random() < (0.3 if importance < 0.5 else 0.08),
        )

    def _referee(self, fx: Fixture) -> RefereeProfile:
        r = _rng("referee", fx.id)
        name, yc, rc, fouls, pen, hwp, var = r.choice(D.REFEREES)
        return RefereeProfile(
            name=name, matches=r.randint(120, 380),
            avg_yellow_cards=yc, avg_red_cards=rc, avg_fouls=fouls,
            penalties_per_match=pen, home_win_pct=hwp, var_overturn_rate=var,
        )

    def _weather(self, fx: Fixture) -> WeatherReport:
        r = _rng("weather", fx.id)
        condition = r.choices(
            ["clear", "clear", "rain", "heavy_rain", "wind", "snow", "fog"],
            weights=[40, 20, 18, 6, 10, 3, 3])[0]
        temp = round(r.uniform(-2, 28), 1)
        impact = {
            "clear": "no weather impact expected",
            "rain": "wet surface may slightly favour direct play and increase errors",
            "heavy_rain": "heavy pitch: fewer clean passing sequences, historically ~6% fewer goals",
            "wind": "strong wind disturbs long balls and crosses",
            "snow": "snow slows the game significantly and raises variance",
            "fog": "reduced visibility, marginal impact",
        }[condition]
        return WeatherReport(
            condition=condition, temperature_c=temp,
            wind_kmh=round(r.uniform(2, 38), 1),
            humidity_pct=round(r.uniform(35, 95), 0),
            precipitation_mm=round({"clear": 0, "fog": 0, "wind": 0}.get(condition, r.uniform(1, 18)), 1),
            pitch_condition="heavy" if condition == "heavy_rain" else
                            "wet" if condition == "rain" else
                            "frozen" if condition == "snow" else "good",
            impact_note=impact,
        )

    def _travel(self, home: Team, away: Team, fx: Fixture) -> TravelReport:
        r = _rng("travel", fx.id)
        km = round(r.uniform(80, 1900), 0)
        return TravelReport(
            away_travel_km=km,
            timezone_shift_h=0 if km < 1200 else r.choice([0, 1]),
            note="long trip for the away side" if km > 1200 else "short travel distance",
        )

    # ------------------------------------------------------------------ odds
    def true_goal_expectations(self, fixture_id: str) -> tuple[float, float]:
        """The latent goal expectations the demo odds are generated from."""
        fx = self._fixture(fixture_id)
        home, away = self._team(fx.home_team_id), self._team(fx.away_team_id)
        r = _rng("truth", fx.id)
        lam_h = 0.28 + 1.35 * (home.attack_rating / 100) * (1.35 - away.defence_rating / 100) + 0.30
        lam_a = 0.24 + 1.30 * (away.attack_rating / 100) * (1.35 - home.defence_rating / 100)
        lam_h *= r.uniform(0.92, 1.08)
        lam_a *= r.uniform(0.92, 1.08)
        return max(0.25, lam_h), max(0.2, lam_a)

    def odds_board(self, fixture_id: str) -> OddsBoard:
        lam_h, lam_a = self.true_goal_expectations(fixture_id)
        r = _rng("odds", fixture_id)
        max_g = 9
        ph = [_poisson_pmf(lam_h, k) for k in range(max_g)]
        pa = [_poisson_pmf(lam_a, k) for k in range(max_g)]
        joint = [[ph[i] * pa[j] for j in range(max_g)] for i in range(max_g)]

        p_home = sum(joint[i][j] for i in range(max_g) for j in range(max_g) if i > j)
        p_draw = sum(joint[i][i] for i in range(max_g))
        p_away = 1 - p_home - p_draw
        p_over = {line: sum(joint[i][j] for i in range(max_g) for j in range(max_g)
                            if i + j > line) for line in (1, 2, 3)}
        p_btts = sum(joint[i][j] for i in range(1, max_g) for j in range(1, max_g))
        p_home_scores = 1 - _poisson_pmf(lam_h, 0)
        p_away_scores = 1 - _poisson_pmf(lam_a, 0)
        p_home_m1 = sum(joint[i][j] for i in range(max_g) for j in range(max_g) if i - j >= 2)
        p_away_p1 = 1 - p_home_m1 - sum(joint[i][j] for i in range(max_g) for j in range(max_g) if i - j == 1)
        p_dnb_home = p_home / (p_home + p_away)
        p_dnb_away = 1 - p_dnb_home

        corners_lam = 9.6 + (lam_h + lam_a - 2.6) * 1.4
        p_corn_over = 1 - sum(_poisson_pmf(corners_lam, k) for k in range(10))
        cards_lam = 4.1
        p_cards_over = 1 - sum(_poisson_pmf(cards_lam, k) for k in range(5))

        defs = [
            ("Match Winner", "Home", "1x2_home", p_home),
            ("Match Winner", "Draw", "1x2_draw", p_draw),
            ("Match Winner", "Away", "1x2_away", p_away),
            ("Double Chance", "Home or Draw", "dc_1x", p_home + p_draw),
            ("Double Chance", "Home or Away", "dc_12", p_home + p_away),
            ("Double Chance", "Draw or Away", "dc_x2", p_draw + p_away),
            ("Over/Under 1.5", "Over 1.5", "ou_1.5_over", p_over[1]),
            ("Over/Under 1.5", "Under 1.5", "ou_1.5_under", 1 - p_over[1]),
            ("Over/Under 2.5", "Over 2.5", "ou_2.5_over", p_over[2]),
            ("Over/Under 2.5", "Under 2.5", "ou_2.5_under", 1 - p_over[2]),
            ("Over/Under 3.5", "Over 3.5", "ou_3.5_over", p_over[3]),
            ("Over/Under 3.5", "Under 3.5", "ou_3.5_under", 1 - p_over[3]),
            ("Both Teams To Score", "Yes", "btts_yes", p_btts),
            ("Both Teams To Score", "No", "btts_no", 1 - p_btts),
            ("Draw No Bet", "Home", "dnb_home", p_dnb_home),
            ("Draw No Bet", "Away", "dnb_away", p_dnb_away),
            ("Team To Score", "Home scores", "ts_home", p_home_scores),
            ("Team To Score", "Away scores", "ts_away", p_away_scores),
            ("Asian Handicap", "Home -1.5", "ah_home_-1.5", p_home_m1),
            ("Asian Handicap", "Away +1.5", "ah_away_+1.5", p_away_p1),
            ("Corners", "Over 9.5 corners", "corners_over_9.5", p_corn_over),
            ("Corners", "Under 9.5 corners", "corners_under_9.5", 1 - p_corn_over),
            ("Cards", "Over 4.5 cards", "cards_over_4.5", p_cards_over),
            ("Cards", "Under 4.5 cards", "cards_under_4.5", 1 - p_cards_over),
        ]

        selections: list[MarketSelection] = []
        now = datetime.now(timezone.utc)
        for market, sel, key, p in defs:
            p = min(0.985, max(0.01, p))
            fair = 1 / p
            books: list[BookmakerOdds] = []
            for bm in D.BOOKMAKERS:
                margin = r.uniform(0.025, 0.075)
                noise = r.uniform(-0.03, 0.05)
                offered = round(max(1.01, fair * (1 - margin) * (1 + noise)), 2)
                books.append(BookmakerOdds(bookmaker=bm, odds=offered, updated_at=now))
            best = max(books, key=lambda b: b.odds)
            avg = sum(b.odds for b in books) / len(books)
            opening = round(best.odds * r.uniform(0.9, 1.12), 2)
            movement = (best.odds - opening) / opening
            selections.append(MarketSelection(
                market=market, selection=sel, market_key=key,
                best_odds=best.odds, best_bookmaker=best.bookmaker,
                avg_odds=round(avg, 2), books=books,
                opening_odds=opening,
                movement_pct=round(movement * 100, 1),
                suspicious_movement=abs(movement) > 0.10,
            ))
        return OddsBoard(fixture_id=fixture_id, selections=selections, updated_at=now)
