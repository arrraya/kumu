"""The data contract a client must satisfy to use Kumu.

Kumu's engine does not depend on any particular provider: the pipeline is an
adapter, and this module is the shape it adapts to. Anything that can produce
per-90 metrics and a match log — Wyscout, Opta, a provider feed, or a club's own
scouting sheets — can fill this in.

Two things deliberately absent from the input:

* `performance_index` is DERIVED, never supplied. It is normalised within a
  position across the whole population, so it cannot be computed from one
  client's squad alone. The client provides raw material; Kumu provides the
  scale.
* `expected_index` on a club is optional for the same reason a club's needs are
  no longer declared: the level a club operates at can be read from the players
  it already has.
"""
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

CONTRACT_VERSION = "1.0"

POSITIONS = {"GK", "CB", "RB", "LB", "CDM", "CM", "CAM", "RW", "LW", "ST"}

# The highest rating the contract will accept. See MatchRecord for why it
# is 30 rather than 10, and why it is a sanity bound rather than a scale.
MAX_RATING = 30.0


class PassingMetrics(BaseModel):
    completion_rate: Optional[float] = Field(None, ge=0, le=1)
    progressive_passes_per_90: Optional[float] = Field(None, ge=0)
    key_passes_per_90: Optional[float] = Field(None, ge=0)
    pass_difficulty_score: Optional[float] = Field(None, ge=0, le=1)


class ShootingMetrics(BaseModel):
    shots_per_90: Optional[float] = Field(None, ge=0)
    xG_per_shot: Optional[float] = Field(None, ge=0)
    conversion_rate: Optional[float] = Field(None, ge=0, le=1)
    goals_per_90: Optional[float] = Field(None, ge=0)
    assists_per_90: Optional[float] = Field(None, ge=0)


class DefensiveMetrics(BaseModel):
    tackles_per_90: Optional[float] = Field(None, ge=0)
    interceptions_per_90: Optional[float] = Field(None, ge=0)
    aerial_duels_won: Optional[float] = Field(None, ge=0)


class MovementMetrics(BaseModel):
    """Tracking data. Absent from most event feeds; the physical profile
    declares itself unavailable rather than inventing values."""

    distance_covered_per_90: Optional[float] = Field(None, ge=0)
    high_intensity_runs: Optional[float] = Field(None, ge=0)
    average_speed: Optional[float] = Field(None, ge=0)


class PlayerMetrics(BaseModel):
    passing: PassingMetrics = Field(default_factory=PassingMetrics)
    shooting: ShootingMetrics = Field(default_factory=ShootingMetrics)
    defensive: DefensiveMetrics = Field(default_factory=DefensiveMetrics)
    movement: Optional[MovementMetrics] = None


class MatchRecord(BaseModel):
    """One appearance. `rating` may be supplied by clients who already have
    their own; when absent Kumu computes it from the counting stats, role-aware.

    One field, two sources, and the ceiling has to admit both. A client's
    own rating sits on the conventional 0-10; Kumu's is uncapped by design,
    because clamping would stack every outlier on the ceiling and leave a
    hat-trick indistinguishable from a one-goal game - the same reasoning
    that made `normalize_indices` compress its tails with tanh rather than
    clip them. `le=10` admitted only the first of the two, so Kumu wrote
    ratings its own contract refused to read back: of 101 A-League players
    loaded, four had a match above 10 and their history could not be
    re-ingested.

    30 is not a scale, it is a sanity bound, and it is set from what the
    three role formulas can actually reach rather than from the one that
    came to mind first. Searched over a grid of extremes, attack tops out
    at 24.6 and midfield and defense at 28.0 - the two that also reward
    progressive passing and defensive work, so they climb highest. A match
    anyone will really play lands near 15. The bound clears the formulas
    and still refuses a client typing 85 for 8.5, which is the error it
    exists to catch: ratings arrive on a 0-10 scale, so a misplaced
    decimal point lands between 50 and 90.

    tests/test_contract.py holds this to the formula rather than to the
    number: it asserts that everything `match_rating` can produce fits
    through this door, so raising one side without the other fails there.
    """

    match_id: Union[str, int]
    date: Optional[str] = None
    minutes: Optional[float] = Field(None, ge=0)
    rating: Optional[float] = Field(None, ge=0, le=MAX_RATING)
    goals: Optional[float] = Field(None, ge=0)
    assists: Optional[float] = Field(None, ge=0)
    key_passes: Optional[float] = Field(None, ge=0)
    shots: Optional[float] = Field(None, ge=0)
    tackles: Optional[float] = Field(None, ge=0)
    interceptions: Optional[float] = Field(None, ge=0)
    progressive_passes: Optional[float] = Field(None, ge=0)
    pass_completion: Optional[float] = Field(None, ge=0, le=1)


class PlayerRecord(BaseModel):
    external_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    position: str
    nationality: Optional[str] = None
    current_team: Optional[str] = None
    age: Optional[int] = Field(None, ge=14, le=50)
    market_value: Optional[float] = Field(None, ge=0)
    metrics: PlayerMetrics = Field(default_factory=PlayerMetrics)
    performance_history: List[MatchRecord] = Field(default_factory=list)


class ClubRecord(BaseModel):
    """The buying club. Only possession and pressing_intensity drive the style
    fit; the rest of the old playing_style fields were decorative."""

    external_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    league: Optional[str] = None
    country: Optional[str] = None
    budget: Optional[float] = Field(None, ge=0)
    formation: Optional[str] = None
    possession: Optional[float] = Field(None, ge=0, le=1)
    pressing_intensity: Optional[float] = Field(None, ge=0, le=1)
    expected_index: Optional[float] = Field(None, ge=0, le=100)
    squad: List[str] = Field(default_factory=list)


class IngestPayload(BaseModel):
    contract_version: str = CONTRACT_VERSION
    source: str = Field(..., min_length=1)
    club: Optional[ClubRecord] = None
    players: List[PlayerRecord] = Field(default_factory=list)


# --- Capability reporting ---------------------------------------------------

MIN_MATCHES_FOR_FORM = 3


def describe_capabilities(payload: IngestPayload) -> Dict[str, Any]:
    """What this payload unlocks, and what it leaves unavailable.

    Product tiers are not invented: they follow from what the data supports.
    Reporting it at load time is the same honesty the reports already apply —
    the coverage badge, moved to the moment the client hands over the data.
    """
    players = payload.players
    total = len(players)

    with_position = sum(1 for p in players if p.position in POSITIONS)
    with_metrics = sum(
        1 for p in players
        if any(v is not None for cat in (p.metrics.passing, p.metrics.shooting,
                                         p.metrics.defensive)
               for v in cat.model_dump().values())
    )
    with_history = sum(1 for p in players if len(p.performance_history) >= MIN_MATCHES_FOR_FORM)
    with_value = sum(1 for p in players if p.market_value)
    with_movement = sum(1 for p in players if p.metrics.movement is not None)

    club = payload.club
    squad_size = len(club.squad) if club else 0
    has_style = bool(club and club.possession is not None
                     and club.pressing_intensity is not None)

    unknown_positions = sorted({p.position for p in players if p.position not in POSITIONS})

    capabilities = {
        "comparison": {
            "enabled": with_position > 0 and with_metrics > 0,
            "requires": "position and at least one metric category",
            "covers": with_metrics,
        },
        "form_and_market": {
            "enabled": with_history > 0,
            "requires": f"a match log of at least {MIN_MATCHES_FOR_FORM} appearances",
            "covers": with_history,
        },
        "squad_fit": {
            "enabled": squad_size > 0,
            "requires": "the buying club's own squad",
            "covers": squad_size,
        },
        "style_fit": {
            "enabled": has_style,
            "requires": "the club's possession and pressing intensity",
        },
        "physical_profile": {
            "enabled": with_movement > 0,
            "requires": "tracking data, which most event feeds do not carry",
            "covers": with_movement,
        },
        "observed_valuation": {
            "enabled": with_value > 0,
            "requires": "market values from the client; otherwise Kumu estimates them",
            "covers": with_value,
        },
    }

    warnings = []
    if unknown_positions:
        warnings.append(
            f"Positions not recognised and ignored: {', '.join(unknown_positions)}. "
            f"Expected one of: {', '.join(sorted(POSITIONS))}."
        )
    if club and not club.squad:
        warnings.append(
            "The club has no squad, so Kumu cannot say whether a signing improves it — "
            "the analysis falls back to comparing against positional peers."
        )
    if not club:
        warnings.append(
            "No buying club supplied: players can be compared to each other, "
            "but not fitted to a destination."
        )
    if with_value == 0:
        warnings.append(
            "No market values supplied. Kumü will estimate them, and every "
            "valuation verdict will be flagged as an internal estimate."
        )

    return {
        "contract_version": payload.contract_version,
        "source": payload.source,
        "players_received": total,
        "club": club.name if club else None,
        "capabilities": capabilities,
        "warnings": warnings,
    }
