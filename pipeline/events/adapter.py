"""
Kumü — SkillCorner open dynamic events -> Kumü's ingest contract
=================================================================

`app/schemas/ingest.py` says the pipeline is an adapter and the schema is
the shape it adapts to. This is that adapter for SkillCorner's open
dynamic-events release: 20 A-League 2024-25 matches, events plus match
sheets.

Two sources per match, and they answer different questions:

    <id>_match.json           the official sheet: who played, how long,
                              who scored, date of birth, role
    <id>_dynamic_events.csv   322 columns of on-ball and off-ball events

WHERE EACH FIGURE COMES FROM
----------------------------
Kumü rates an appearance from eight counting stats. Six of them are in
the data as themselves; two are not, and are stood in for. The
difference is recorded in PROVENANCE and travels with the payload, so a
report can say "estimated" where Kumü is reading a shadow of the thing
rather than the thing.

    goals              measured   match sheet (`goal`), not inferred
    minutes            measured   match sheet (`minutes_played`)
    shots              measured   possession ending in `shot`
    pass_completion    measured   `pass_outcome` successful / attempted
    progressive_passes measured   pass breaking a defensive line
    key_passes         estimated  last completed pass before a shot
    assists            estimated  the same, before a scoring shot
    tackles            estimated  `direct_regain` + `direct_disruption`
    interceptions      ABSENT     no counterpart in this model

A tackle in SkillCorner's vocabulary does not exist: what exists is an
engagement and what it ended in. Winning the ball with a direct
intervention is the nearest true thing, and it is not the same thing.

THREE FIGURES THIS ADAPTER REFUSED
----------------------------------
Each of these had an obvious column and the obvious column was wrong.

`interceptions` looked like `indirect_regain`, and that field ran at 66
per team per match against a real 8-12. It does not mark an
interception: it marks that the team got the ball back at some point
after this engagement, credited to every player who pressed. Kumü sums
tackles and interceptions into one defensive term, so loading it would
have handed the median defender eight phantom ball-wins per 90 and let
the defensive term swamp pass completion in `match_rating`. There is no
interception in an engagement-based model. It is left absent.

`key_passes` looked like `lead_to_shot`, which ran at 36 per team per
match against a real 8-12: it flags every possession in a chain that
ended in a shot, not the pass that made it. Walking back from each shot
to the pass before it gives one key pass per shot at most, which is
what the term means. Measured-but-wrong lost to estimated-but-right.

`pass_difficulty_score` looked like `xpass_completion`, which is
populated on `passing_option` rows and empty on every possession. Absent.

NOT TAKEN, ON PURPOSE
---------------------
`xthreat` and `xpass_completion` are populated on `passing_option` rows,
not on the possessions, so `pass_difficulty_score` is left absent rather
than computed from the wrong rows. `aerial_duels_won` has no counterpart
at all. Market value has none either: these players carry no price here.
"""

import collections
import csv
import datetime
import json
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

PROVENANCE = {
    "goals": "measured",
    "minutes": "measured",
    "shots": "measured",
    "pass_completion": "measured",
    "progressive_passes": "measured",
    "key_passes": "estimated",
    "assists": "estimated",
    "tackles": "estimated",
    # Absent on purpose. See the module docstring: the field that looked
    # like an interception was a pressure chain, four times too large.
    "interceptions": "absent",
}

# SkillCorner's role vocabulary, as it appears in `player_role.name`.
# Kumü's PROVIDER_POSITION_MAP is seeded with StatsBomb's names, and the
# two agree on most of them but not all: SkillCorner says "Right Winger"
# where StatsBomb says "Right Wing", and names a lone holding midfielder
# "Defensive Midfield" rather than "Center Defensive Midfield". The
# names that differ are added to the map in scoring.py; this set is what
# this adapter refuses to pass on.
#
# "Substitute" is a role for a player who did not come on. He has no
# position because he had no position, and an appearance of zero minutes
# is not an appearance.
UNPLAYED_ROLES = {"Substitute"}

ENGAGEMENT_DIRECT = {"direct_regain", "direct_disruption"}
# `indirect_*` end types are deliberately unused: see the docstring.

# A league's own name is not in the open release; the competition edition
# id is. Declared here rather than guessed per match.
LEAGUE = "A-League Men"
COUNTRY = "Australia"
SOURCE = "skillcorner_open"


def _truthy(value: Any) -> bool:
    """The CSV writes booleans as the strings True/False, and blank for
    not-applicable. Only an explicit True counts."""
    return str(value).strip() == "True"


def _age_at(birthday: Optional[str], match_date: Optional[str]) -> Optional[int]:
    """Age on the day of the match, not age today.

    A match log that spans a season would otherwise hand every
    appearance the same age, which is the kind of quietly wrong number
    that survives review because it looks reasonable.
    """
    if not birthday or not match_date:
        return None
    try:
        born = datetime.date.fromisoformat(str(birthday)[:10])
        played = datetime.date.fromisoformat(str(match_date)[:10])
    except ValueError:
        return None
    years = played.year - born.year
    if (played.month, played.day) < (born.month, born.day):
        years -= 1
    return years if 14 <= years <= 50 else None


def read_match_sheet(path: str) -> Tuple[Dict[str, Any], Dict[int, Dict[str, Any]]]:
    """The official sheet: the match, and every player who was named.

    Returns (meta, by_player_id). Players whose role is Substitute, or
    who logged no minutes, are left out: they were named, not played.
    """
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)

    teams = {}
    for side in ("home_team", "away_team"):
        team = raw.get(side) or {}
        if team.get("id") is not None:
            teams[int(team["id"])] = (
                team.get("name") or team.get("short_name") or str(team["id"])
            )

    meta = {
        "match_id": raw.get("id"),
        "date": (raw.get("date_time") or "")[:10] or None,
        "teams": teams,
        "home_score": raw.get("home_team_score"),
        "away_score": raw.get("away_team_score"),
    }

    players: Dict[int, Dict[str, Any]] = {}
    for entry in raw.get("players") or []:
        pid = entry.get("id")
        if pid is None:
            continue
        role = (entry.get("player_role") or {}).get("name")
        if role in UNPLAYED_ROLES:
            continue
        total = ((entry.get("playing_time") or {}).get("total") or {})
        minutes = total.get("minutes_played")
        if not minutes:
            continue

        team_id = entry.get("team_id")
        players[int(pid)] = {
            "player_id": int(pid),
            "name": (
                entry.get("short_name")
                or " ".join(
                    p for p in (entry.get("first_name"), entry.get("last_name")) if p
                )
                or str(pid)
            ),
            "role": role,
            "minutes": float(minutes),
            "goals": float(entry.get("goal") or 0),
            "team_id": int(team_id) if team_id is not None else None,
            "team_name": teams.get(int(team_id)) if team_id is not None else None,
            "age": _age_at(entry.get("birthday"), meta["date"]),
        }
    return meta, players


def _read_events(path: str) -> List[Dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda r: int(r["index"] or 0))
    return rows


def derive_pass_credits(
    events: Iterable[Dict[str, str]],
) -> Tuple[collections.Counter, collections.Counter]:
    """Who played the last pass before a shot, and before a goal.

    Walks back from each shot to the possession immediately before it.
    If that possession was a completed pass by a team-mate, the passer
    is credited; if the previous touch was the shooter's own, or the
    other team's, nobody is. Returns (key_passes, assists), the second
    being the subset where the shot went in — so a player's assists
    never exceed his key passes, as the terms require.

    Penalties, rebounds and solo goals correctly credit nobody, which
    is why this yields fewer assists than there were goals.
    """
    rows = list(events)
    key_passes: collections.Counter = collections.Counter()
    assists: collections.Counter = collections.Counter()

    for position, row in enumerate(rows):
        is_shot = (
            row["event_type"] == "player_possession"
            and row["end_type"] == "shot"
        )
        if not is_shot:
            continue
        for previous in reversed(rows[:position]):
            if previous["event_type"] != "player_possession":
                continue
            creator = previous["player_id"]
            credited = (
                creator
                and previous["team_id"] == row["team_id"]
                and previous["end_type"] == "pass"
                and previous["pass_outcome"] == "successful"
                and creator != row["player_id"]
            )
            if credited:
                key_passes[int(creator)] += 1
                if _truthy(row["lead_to_goal"]):
                    assists[int(creator)] += 1
            break
    return key_passes, assists


def per_player_match(events: List[Dict[str, str]],
                     sheet: Dict[int, Dict[str, Any]],
                     meta: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    """One appearance record per player, in the shape MatchRecord wants.

    Only players on the sheet get a record. A player with events but no
    minutes is a data disagreement, not a half-appearance, and is
    dropped rather than guessed at.
    """
    counts: Dict[int, collections.Counter] = collections.defaultdict(
        collections.Counter
    )

    for row in events:
        kind = row["event_type"]

        if kind == "player_possession":
            pid = row["player_id"] or row["player_in_possession_id"]
            if not pid:
                continue
            tally = counts[int(pid)]
            if row["end_type"] == "shot":
                tally["shots"] += 1
            if row["end_type"] == "pass":
                tally["passes"] += 1
                if row["pass_outcome"] == "successful":
                    tally["passes_completed"] += 1
                if (
                    _truthy(row["first_line_break"])
                    or _truthy(row["second_last_line_break"])
                    or _truthy(row["last_line_break"])
                ):
                    tally["progressive_passes"] += 1

        elif kind == "on_ball_engagement":
            pid = row["player_id"]
            if not pid:
                continue
            tally = counts[int(pid)]
            if row["end_type"] in ENGAGEMENT_DIRECT:
                tally["tackles"] += 1

    key_passes, assists = derive_pass_credits(events)

    records: Dict[int, Dict[str, Any]] = {}
    for pid, player in sheet.items():
        tally = counts.get(pid, collections.Counter())
        attempted = tally["passes"]
        record = {
            "match_id": str(meta["match_id"]),
            "date": meta["date"],
            "minutes": round(player["minutes"], 1),
            "goals": player["goals"],
            "assists": float(assists.get(pid, 0)),
            "key_passes": float(key_passes.get(pid, 0)),
            "shots": float(tally["shots"]),
            "tackles": float(tally["tackles"]),
            "progressive_passes": float(tally["progressive_passes"]),
        }
        if attempted:
            record["pass_completion"] = round(
                tally["passes_completed"] / attempted, 3
            )
        records[pid] = record
    return records


def find_matches(root: str) -> List[Tuple[str, str]]:
    """Locate (sheet, events) pairs under `root`, in either layout.

    SkillCorner's repository puts each match in its own folder; a zip
    unpacked flat puts all forty files side by side. Both are the same
    release and neither is wrong, so both are read. A match missing
    either half is skipped rather than half-loaded.
    """
    found: Dict[str, Dict[str, str]] = {}

    def note(path: str, name: str) -> None:
        if name.endswith("_match.json"):
            found.setdefault(name[: -len("_match.json")], {})["sheet"] = path
        elif name.endswith("_dynamic_events.csv"):
            key = name[: -len("_dynamic_events.csv")]
            found.setdefault(key, {})["events"] = path

    for entry in sorted(os.listdir(root)):
        full = os.path.join(root, entry)
        if os.path.isdir(full):
            for name in sorted(os.listdir(full)):
                note(os.path.join(full, name), name)
        else:
            note(full, entry)

    return [
        (pair["sheet"], pair["events"])
        for _match_id, pair in sorted(found.items())
        if "sheet" in pair and "events" in pair
    ]


def read_release(root: str) -> Dict[int, Dict[str, Any]]:
    """Every match in the release, folded into one player per key.

    Returns player_id -> {name, role counts, appearances, ages, history}.
    `appearances` keeps each match's club and role against its date, so
    `current_team` can be the club he is at now rather than the club he
    appeared for most often. A season sample spans a transfer window:
    three matches at the selling club and one at the buying club is a
    player who has moved, and in a transfer product listing him at the
    club he left is the single most damaging field to get wrong.
    """
    players: Dict[int, Dict[str, Any]] = {}

    for sheet_path, events_path in find_matches(root):
        meta, sheet = read_match_sheet(sheet_path)
        records = per_player_match(_read_events(events_path), sheet, meta)

        for pid, record in records.items():
            player = players.setdefault(
                pid,
                {
                    "player_id": pid,
                    "name": sheet[pid]["name"],
                    "roles": collections.Counter(),
                    "appearances": [],
                    "ages": [],
                    "history": [],
                },
            )
            player["name"] = sheet[pid]["name"] or player["name"]
            if sheet[pid]["role"]:
                player["roles"][sheet[pid]["role"]] += 1
            player["appearances"].append({
                "date": record["date"] or "",
                "match_id": record["match_id"],
                "team": sheet[pid]["team_name"],
                "role": sheet[pid]["role"],
            })
            if sheet[pid]["age"] is not None:
                player["ages"].append(sheet[pid]["age"])
            player["history"].append(record)

    for player in players.values():
        player["history"].sort(key=lambda r: (r["date"] or "", r["match_id"]))
        player["appearances"].sort(key=lambda a: (a["date"], a["match_id"]))
    return players


def latest_club(player: Dict[str, Any]) -> Optional[str]:
    """The club of his most recent appearance."""
    for appearance in reversed(player.get("appearances") or []):
        if appearance.get("team"):
            return appearance["team"]
    return None


def usual_role(player: Dict[str, Any]) -> Optional[str]:
    """His most frequent role, ties broken by the most recent of them.

    Position should describe where he usually plays, not where he
    happened to play last. But a dead heat must not be settled by
    whatever order a Counter happens to iterate in, or the same input
    could load two different positions on two different days.
    """
    roles = player.get("roles") or {}
    if not roles:
        return None
    top = max(roles.values())
    tied = {role for role, count in roles.items() if count == top}
    if len(tied) == 1:
        return next(iter(tied))
    for appearance in reversed(player.get("appearances") or []):
        if appearance.get("role") in tied:
            return appearance["role"]
    return sorted(tied)[0]


def _per_90(history: List[Dict[str, Any]], field: str) -> Optional[float]:
    minutes = sum(h.get("minutes") or 0 for h in history)
    if minutes <= 0:
        return None
    total = sum(h.get(field) or 0 for h in history)
    return round(total * 90.0 / minutes, 3)


def _weighted_completion(history: List[Dict[str, Any]]) -> Optional[float]:
    """Completion over the whole sample, not the mean of per-match rates.

    Averaging rates gives a player's twelve-pass cameo the same weight
    as his ninety-pass match. The same inequality that biased cadence in
    the pose metrics: the mean of ratios is not the ratio of the sums.
    """
    weighted = 0.0
    minutes = 0.0
    for entry in history:
        rate = entry.get("pass_completion")
        played = entry.get("minutes") or 0
        if rate is None or played <= 0:
            continue
        weighted += rate * played
        minutes += played
    if minutes <= 0:
        return None
    return round(weighted / minutes, 3)


def build_metrics(history: List[Dict[str, Any]],
                  movement: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """The per-90 aggregate, with movement only where it was measured.

    `movement` stays absent unless pose was actually read for this
    player. MovementMetrics exists to declare itself unavailable, and
    this is the call site that has to honour that.
    """
    metrics: Dict[str, Any] = {
        "passing": {
            "completion_rate": _weighted_completion(history),
            "progressive_passes_per_90": _per_90(history, "progressive_passes"),
            "key_passes_per_90": _per_90(history, "key_passes"),
        },
        "shooting": {
            "shots_per_90": _per_90(history, "shots"),
            "goals_per_90": _per_90(history, "goals"),
            "assists_per_90": _per_90(history, "assists"),
        },
        "defensive": {
            "tackles_per_90": _per_90(history, "tackles"),
        },
    }
    for group in list(metrics):
        metrics[group] = {k: v for k, v in metrics[group].items() if v is not None}
        if not metrics[group]:
            del metrics[group]
    if movement:
        metrics["movement"] = movement
    return metrics


def build_payloads(players: Dict[int, Dict[str, Any]],
                   min_matches: int = 3,
                   movement_by_id: Optional[Dict[int, Dict[str, float]]] = None,
                   ) -> List[Dict[str, Any]]:
    """One payload per club, carrying only players with enough matches.

    Kumü's index needs three appearances and says so in
    MIN_MATCHES_FOR_INDEX. A player below that would land with a history
    and no index, which reads on screen as a broken record rather than a
    thin one, so he is not loaded at all.
    """
    movement_by_id = movement_by_id or {}
    by_club: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)

    for pid, player in players.items():
        history = player["history"]
        if len(history) < min_matches:
            continue
        role = usual_role(player)
        if not role:
            continue
        club = latest_club(player)
        if not club:
            continue

        by_club[club].append({
            "external_id": f"sc_{pid}",
            "name": player["name"],
            "position": role,
            "current_team": club,
            "age": max(player["ages"]) if player["ages"] else None,
            "metrics": build_metrics(history, movement_by_id.get(pid)),
            "performance_history": history,
        })

    payloads = []
    for club, squad in sorted(by_club.items()):
        payloads.append({
            "contract_version": "1.0",
            "source": SOURCE,
            "club": {
                "external_id": "sc_club_" + club.lower().replace(" ", "_"),
                "name": club,
                "league": LEAGUE,
                "country": COUNTRY,
                "squad": [p["external_id"] for p in squad],
            },
            "players": squad,
        })
    return payloads
