"""Pydantic schemas shared by the data layer, the analysis engine and the API."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

class Sport(str, Enum):
    FOOTBALL = "football"
    # The provider/engine layers are sport-agnostic where possible so new
    # sports (basket, tennis, ...) can be added as additional engines.


class League(BaseModel):
    id: str
    name: str
    country: str
    sport: Sport = Sport.FOOTBALL


class Team(BaseModel):
    id: str
    name: str
    short_name: str
    league_id: str
    # long-run strength ratings on a ~[0, 100] scale
    attack_rating: float
    defence_rating: float
    elo: float


class Fixture(BaseModel):
    id: str
    league_id: str
    home_team_id: str
    away_team_id: str
    kickoff_utc: datetime
    venue: str
    round: str = ""
    status: str = "scheduled"


# ---------------------------------------------------------------------------
# Team & player statistics
# ---------------------------------------------------------------------------

class FormWindow(BaseModel):
    """Aggregated statistics over the last N matches."""
    matches: int
    wins: int
    draws: int
    losses: int
    goals_for: float
    goals_against: float
    xg_for: float
    xg_against: float
    shots: float
    shots_on_target: float
    big_chances_created: float
    big_chances_conceded: float
    possession_pct: float
    pass_accuracy_pct: float
    ppda: float                      # passes per defensive action (pressing)
    recoveries: float
    corners_for: float
    corners_against: float
    cards_for: float
    cards_against: float
    deep_completions: float
    passes_final_third: float
    dangerous_attacks: float
    points_per_game: float


class VenueSplit(BaseModel):
    """Home vs away performance split."""
    matches: int
    points_per_game: float
    goals_for_avg: float
    goals_against_avg: float
    xg_for_avg: float
    xg_against_avg: float
    win_pct: float
    clean_sheet_pct: float
    btts_pct: float
    over25_pct: float


class PlayerStats(BaseModel):
    goals: int = 0
    assists: int = 0
    xg: float = 0.0
    xa: float = 0.0
    pass_accuracy_pct: float = 0.0
    shot_accuracy_pct: float = 0.0
    tackles_won_pct: float = 0.0
    dribbles_success_pct: float = 0.0
    fouls_per90: float = 0.0
    yellow_cards: int = 0
    red_cards: int = 0
    avg_rating: float = 6.0
    minutes_last_30d: int = 0
    form_trend: str = "stable"       # improving | stable | declining


class Player(BaseModel):
    id: str
    name: str
    team_id: str
    position: str                    # GK / DF / MF / FW
    importance: float = Field(ge=0, le=1, description="share of team output")
    stats: PlayerStats = PlayerStats()


class AvailabilityStatus(str, Enum):
    INJURED = "injured"
    SUSPENDED = "suspended"
    DOUBTFUL = "doubtful"
    YELLOW_CARD_RISK = "yellow_card_risk"   # one booking from suspension
    RETURNED = "returned"                   # late fitness recovery


class AvailabilityItem(BaseModel):
    player: Player
    status: AvailabilityStatus
    detail: str = ""
    expected_return: Optional[str] = None


class SquadReport(BaseModel):
    team_id: str
    availability: list[AvailabilityItem] = []
    probable_lineup: list[str] = []          # player names, 4-3-3 order
    lineup_confirmed: bool = False
    formation: str = "4-3-3"
    rotation_risk: float = Field(ge=0, le=1, default=0.1)
    fatigue_index: float = Field(ge=0, le=1, default=0.2)
    days_rest: int = 6
    european_fixture_within_4d: bool = False
    key_players_in_form: list[str] = []
    key_players_out_of_form: list[str] = []


class TacticalProfile(BaseModel):
    team_id: str
    formation: str
    probable_formation: str
    style: str                       # possession | counter | high-press | low-block | balanced
    pressing_intensity: float = Field(ge=0, le=1)
    defensive_line_height: float = Field(ge=0, le=1)
    counter_attack_threat: float = Field(ge=0, le=1)
    crossing_volume: float = Field(ge=0, le=1)
    set_piece_threat: float = Field(ge=0, le=1)
    set_piece_weakness: float = Field(ge=0, le=1)
    strengths: list[str] = []
    weaknesses: list[str] = []


class H2HSummary(BaseModel):
    window: int
    played: int
    home_team_wins: int
    draws: int
    away_team_wins: int
    avg_goals: float
    over25_pct: float
    under25_pct: float
    btts_pct: float
    notes: list[str] = []


class MotivationFactor(BaseModel):
    team_id: str
    context: list[str] = []          # e.g. "title race", "relegation battle", "derby"
    importance: float = Field(ge=0, le=1, description="0 = dead rubber, 1 = final")
    turnover_expected: bool = False


class RefereeProfile(BaseModel):
    name: str
    matches: int
    avg_yellow_cards: float
    avg_red_cards: float
    avg_fouls: float
    penalties_per_match: float
    home_win_pct: float
    var_overturn_rate: float = 0.0


class WeatherReport(BaseModel):
    condition: str                   # clear | rain | heavy_rain | snow | wind | fog
    temperature_c: float
    wind_kmh: float
    humidity_pct: float
    precipitation_mm: float
    pitch_condition: str = "good"    # good | wet | heavy | frozen
    impact_note: str = ""


class TravelReport(BaseModel):
    away_travel_km: float = 0.0
    timezone_shift_h: int = 0
    note: str = ""


class MatchContext(BaseModel):
    """Everything the engine knows about a single fixture."""
    fixture: Fixture
    league: League
    home_team: Team
    away_team: Team
    home_form: dict[int, FormWindow]         # keyed by window: 5, 10, 20
    away_form: dict[int, FormWindow]
    home_venue_split: VenueSplit
    away_venue_split: VenueSplit
    home_squad: SquadReport
    away_squad: SquadReport
    home_tactics: TacticalProfile
    away_tactics: TacticalProfile
    h2h: dict[int, H2HSummary]               # keyed by window: 5, 10, 20
    home_motivation: MotivationFactor
    away_motivation: MotivationFactor
    referee: RefereeProfile
    weather: WeatherReport
    travel: TravelReport
    attendance_expected: int = 0


# ---------------------------------------------------------------------------
# Odds & markets
# ---------------------------------------------------------------------------

class BookmakerOdds(BaseModel):
    bookmaker: str
    odds: float
    updated_at: datetime


class MarketSelection(BaseModel):
    market: str                      # e.g. "Match Winner", "Over/Under 2.5"
    selection: str                   # e.g. "Home", "Over 2.5"
    market_key: str                  # engine key, e.g. "1x2_home", "ou_2.5_over"
    best_odds: float
    best_bookmaker: str
    avg_odds: float
    books: list[BookmakerOdds] = []
    opening_odds: float = 0.0
    movement_pct: float = 0.0        # (best - opening) / opening
    suspicious_movement: bool = False


class OddsBoard(BaseModel):
    fixture_id: str
    selections: list[MarketSelection]
    updated_at: datetime


# ---------------------------------------------------------------------------
# Engine output
# ---------------------------------------------------------------------------

class SimulationSummary(BaseModel):
    runs: int
    home_win: float
    draw: float
    away_win: float
    over_15: float
    over_25: float
    over_35: float
    under_25: float
    btts: float
    avg_goals: float
    avg_corners: float
    avg_cards: float
    top_correct_scores: list[tuple[str, float]] = []
    home_expected_goals: float = 0.0
    away_expected_goals: float = 0.0


class ModelProbability(BaseModel):
    model: str
    probabilities: dict[str, float]  # market_key -> probability
    weight: float


class FactorImpact(BaseModel):
    factor: str
    direction: str                   # favorable | risk | neutral
    impact: float                    # signed contribution estimate
    evidence: str


class BetCandidate(BaseModel):
    market: str
    selection: str
    market_key: str
    offered_odds: float
    bookmaker: str
    estimated_probability: float
    fair_odds: float
    value_margin_pct: float          # (p * odds - 1) * 100
    confidence: float                # 0-100 composite reliability
    confidence_label: str            # Very High / High / Medium / Low
    odds_distance: float             # |offered - target| / target
    kelly_fraction: float = 0.0
    model_agreement: float = 0.0     # std-dev based agreement across models


class BetRecommendation(BaseModel):
    fixture_id: str
    match_label: str
    kickoff_utc: datetime
    league: str
    target_odds: float
    pick: BetCandidate
    alternatives: list[BetCandidate]
    reasoning: list[str]
    favorable_factors: list[FactorImpact]
    risk_factors: list[FactorImpact]
    simulation: SimulationSummary
    model_breakdown: list[ModelProbability]
    stats_used: dict[str, str]       # headline stats surfaced in the UI
    disclaimer: str


class AnalysisRequest(BaseModel):
    sport: Sport = Sport.FOOTBALL
    league_id: Optional[str] = None
    fixture_id: Optional[str] = None
    date: Optional[str] = None       # ISO date filter when no fixture chosen
    target_odds: float = Field(gt=1.0, le=1000)
