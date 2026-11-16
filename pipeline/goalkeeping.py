"""
Kumü — derive goalkeeping from StatsBomb events
================================================

    python3 pipeline/goalkeeping.py                      # the whole tournament
    python3 pipeline/goalkeeping.py --match 3857254      # one match
    python3 pipeline/goalkeeping.py --out gk.json

Kumü's reference population had no goalkeepers at all. Two places
skipped them by name, silently and without agreeing with the client
path, and the reason was real: every metric Kumu held described
outfield play, so a keeper was rated on his pass completion. The fields
that would rate him properly were declared in the contract before
anything filled them. This fills them.

HOW EACH FIGURE IS REACHED
--------------------------
Every shot produces a `Goal Keeper` event from the keeper facing it, and
that event names him, so attribution needs no guessing about who was on
the pitch. The event links to the shot through `related_events`, which
carries the expected goals.

The keeper's own event type says what happened, and it is read rather
than the shot's outcome, because the type already distinguishes the
cases that matter. The full vocabulary was counted across all 64
matches rather than assumed - the first version of this file looked for
saves and shots faced only, missed that a goal is its own event type,
and so had every keeper in the tournament on a 100% save rate with
`goals_prevented` measuring nothing but how often he was shot at. The
ranking it produced put the Golden Glove 25th of 28.

    saves                   Shot Saved, Penalty Saved, Shot Saved to
                            Post, Shot Saved Off Target
    goals_conceded          Goal Conceded, Penalty Conceded
    shots_on_target_faced   the two above: a shot he saved or conceded
                            is by definition one he had to deal with
    claims                  Collected, Punch, Smother
    sweeper_actions         Keeper Sweeper
    goals_prevented         expected goals of those shots, minus the
                            goals conceded

`Shot Faced` is the rest - blocked by a defender, off target, wayward,
against the post - and none of it reaches the keeper, so none of it
counts for or against him.

The bare type `Save` appears six times in the tournament and links to no
shot, so there is no way to tell what it faced. Left out, and said here
rather than folded in silently.

Shootouts are excluded. StatsBomb records them as period 5, and they
hold 26 of the 195 penalties conceded and 10 of the 15 saved: a separate
contest, decided under different conditions, which would otherwise
dominate the record of every keeper whose team reached one.

WHAT `goals_prevented` IS AND IS NOT
------------------------------------
It is built from `shot_statsbomb_xg`, which is expected goals from
BEFORE the shot: where it was struck from, with what, under how much
pressure. What a goalkeeping analyst means by goals prevented uses
post-shot expected goals, which also knows where in the goal the ball
was heading - and dealing with where it was heading is the job.
StatsBomb's open data does not carry that.

Taken raw, the difference is not a rough edge, it is a bias that swamps
the measurement. Pre-shot xG averages over every outcome, most of which
miss the target. Once a shot IS on target it is far more likely to go
in: across the tournament, 510 on-target shots produced 169 goals, a
conversion of 33.1%, while their pre-shot xG expected 17.4%. Charging a
keeper the difference made all 28 of them negative, by 0.61 goals a
match each. The first run of this file did exactly that, and what it
ranked was not goalkeeping but how badly pre-shot xG understates a shot
on target - a property of the data, identical for everyone.

So the expectation is rescaled by a factor the population supplies: the
goals actually conceded divided by the pre-shot xG of the shots that
caused them. It comes out near 1.9 here and is recomputed for whatever
set is processed rather than written down, because a constant fitted to
one tournament is a fudge factor wearing a measurement's clothes.

That makes this **goals prevented against an average goalkeeper facing
the same chances**, not an absolute count, and it sums to zero across
the population by construction. A keeper beaten by an unstoppable
finish into the top corner is still charged for it, because nothing
here knows where the ball went. Over a tournament that noise averages
down; over three matches it does not, which is one more reason the
index asks for three appearances before it says anything.
"""

import argparse
import collections
import hashlib
import json
import os
import sys

# Resolved from this file, not from the working directory. The two
# `sys.path.insert(0, "backend")` calls this replaces only worked when the
# script happened to be run from the repository root, and failed with
# "No module named 'app'" from anywhere else - including the folder the
# script itself lives in.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(REPO, "backend") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "backend"))

WORLD_CUP = {"competition_id": 43, "season_id": 106}

# Counted across all 64 matches of the tournament, not assumed. Anything
# not listed here is deliberately not counted, and `derive_match` reports
# what it saw and did not recognise so a new vocabulary cannot pass
# unnoticed the way `Goal Conceded` did.
SAVE_TYPES = {"Shot Saved", "Penalty Saved",
              "Shot Saved to Post", "Shot Saved Off Target"}
GOAL_TYPES = {"Goal Conceded", "Penalty Conceded"}
CLAIM_TYPES = {"Collected", "Punch", "Smother"}
SWEEPER_TYPES = {"Keeper Sweeper"}
# Not his to answer for: blocked by a defender, off target, wayward, post.
FACED_TYPES = {"Shot Faced"}
# Six in the tournament, linked to no shot, so there is nothing to read.
IGNORED_TYPES = {"Save"}

# StatsBomb's period for a shootout. A separate contest, excluded.
SHOOTOUT_PERIOD = 5


def _match_ids(sb, explicit=None):
    if explicit:
        return list(explicit)
    matches = sb.matches(**WORLD_CUP)
    return sorted(int(m) for m in matches["match_id"].tolist())


def _minutes_by_player(events):
    """Minutes approximated from a player's own first and last event.

    The same approximation `pipeline/metrics.py` already uses, kept
    identical on purpose: two different minute figures for the same
    appearance would put per-90 numbers from the two pipelines on
    different footings without anything saying so.
    """
    out = {}
    for player, pev in events.groupby("player"):
        minutes = pev["minute"]
        if len(minutes):
            out[player] = float(max(minutes.max() - minutes.min(), 1))
    return out


def derive_match(events) -> dict:
    """Per-goalkeeper figures for one match's events."""
    shots = events[events["type"] == "Shot"].set_index("id")
    keeper_events = events[events["type"] == "Goal Keeper"]
    minutes = _minutes_by_player(events)

    tally = collections.defaultdict(collections.Counter)
    expected = collections.defaultdict(float)
    teams = {}
    unlinked = 0
    unknown = collections.Counter()

    for _, event in keeper_events.iterrows():
        keeper = event.get("player")
        if not isinstance(keeper, str):
            continue
        if int(event.get("period") or 1) >= SHOOTOUT_PERIOD:
            continue
        teams[keeper] = event.get("team")
        kind = event.get("goalkeeper_type")
        counts = tally[keeper]

        if kind in CLAIM_TYPES:
            counts["claims"] += 1
            continue
        if kind in SWEEPER_TYPES:
            counts["sweeper_actions"] += 1
            continue
        if kind in FACED_TYPES or kind in IGNORED_TYPES:
            continue
        saved = kind in SAVE_TYPES
        conceded = kind in GOAL_TYPES
        if not (saved or conceded):
            # A type this file has never seen. Reported rather than
            # skipped: `Goal Conceded` was missed exactly this way, and
            # the result looked plausible enough to ship.
            if isinstance(kind, str):
                unknown[kind] += 1
            continue

        # He saved it or it went in, so he had to deal with it.
        counts["shots_on_target_faced"] += 1
        counts["saves" if saved else "goals_conceded"] += 1

        related = event.get("related_events")
        linked = [i for i in (related if isinstance(related, list) else [])
                  if i in shots.index]
        if linked:
            expected[keeper] += float(
                shots.loc[linked[0]].get("shot_statsbomb_xg") or 0.0)
        else:
            # Counted as faced, but with no chance quality to credit him
            # for. Reported so the gap is visible.
            unlinked += 1

    # A keeper who played and faced nothing still played: his zeros are
    # figures. Seed him from the squad so he is not mistaken for absent.
    for keeper in events[events["position"] == "Goalkeeper"]["player"].dropna().unique():
        if isinstance(keeper, str):
            tally[keeper]
            teams.setdefault(keeper, None)

    records = {}
    for keeper, counts in tally.items():
        conceded = counts["goals_conceded"]
        records[keeper] = {
            "team": teams.get(keeper),
            "minutes": minutes.get(keeper),
            "saves": float(counts["saves"]),
            "shots_on_target_faced": float(counts["shots_on_target_faced"]),
            "goals_conceded": float(conceded),
            # Raw, unscaled. `derive` turns it into goals_prevented once it
            # knows the population's conversion rate; a single match cannot
            # supply one.
            "expected_on_target_faced": round(expected[keeper], 4),
            "claims": float(counts["claims"]),
            "sweeper_actions": float(counts["sweeper_actions"]),
            "pass_completion": _pass_completion(events, keeper),
        }
    return {"keepers": records, "unlinked": unlinked, "unknown": dict(unknown)}


def _pass_completion(events, player):
    passes = events[(events["type"] == "Pass") & (events["player"] == player)]
    if not len(passes):
        return None
    completed = passes["pass_outcome"].isna().sum()
    return round(float(completed) / len(passes), 3)


# Below this many on-target shots the population cannot fix its own
# scale, and a figure derived from a handful of them would be noise with
# a decimal point.
MIN_SHOTS_FOR_SCALE = 100


def conversion_scale(keepers) -> float:
    """How much the pre-shot expectation has to grow to match reality.

    Goals actually conceded, over the pre-shot expected goals of the
    shots that caused them. Derived from whatever set is being processed,
    so it travels to another competition instead of carrying this
    tournament's number around. Returns 1.0 on too small a sample, which
    leaves the expectation uncorrected and the figure visibly wrong
    rather than invisibly fitted.
    """
    goals = expected = shots = 0.0
    for entry in keepers.values():
        for record in entry["history"]:
            goals += record["goals_conceded"]
            expected += record.get("expected_on_target_faced", 0.0)
            shots += record["shots_on_target_faced"]
    if shots < MIN_SHOTS_FOR_SCALE or expected <= 0:
        return 1.0
    return goals / expected


def per_90(history) -> dict:
    """The GoalkeepingMetrics shape, over a keeper's whole sample."""
    minutes = sum(h.get("minutes") or 0 for h in history)
    if minutes <= 0:
        return {}
    scale = 90.0 / minutes
    faced = sum(h["shots_on_target_faced"] for h in history)
    saves = sum(h["saves"] for h in history)
    return {
        "saves_per_90": round(saves * scale, 3),
        # Over the whole sample, not the mean of per-match rates: a keeper
        # who faced one shot in a cameo would otherwise weigh as much as one
        # who faced nine.
        "save_percentage": round(saves / faced, 3) if faced else None,
        "goals_prevented_per_90": round(
            sum(h["goals_prevented"] for h in history) * scale, 3),
        "claims_per_90": round(sum(h["claims"] for h in history) * scale, 3),
        "sweeper_actions_per_90": round(
            sum(h["sweeper_actions"] for h in history) * scale, 3),
    }


def derive(match_ids=None, progress=True) -> dict:
    """Every goalkeeper across the matches, with history and per-90."""
    from statsbombpy import sb

    ids = _match_ids(sb, match_ids)
    keepers = collections.defaultdict(
        lambda: {"team": None, "history": []})
    unlinked = 0
    unknown = collections.Counter()

    for n, match_id in enumerate(ids, 1):
        if progress and n % 10 == 0:
            print(f"  [{n}/{len(ids)}]", file=sys.stderr)
        events = sb.events(match_id=match_id)
        result = derive_match(events)
        unlinked += result["unlinked"]
        unknown.update(result["unknown"])
        for keeper, record in result["keepers"].items():
            entry = keepers[keeper]
            entry["team"] = record.pop("team") or entry["team"]
            record["match_id"] = str(match_id)
            entry["history"].append(record)

    scale = conversion_scale(keepers)
    for entry in keepers.values():
        for record in entry["history"]:
            expected = record.pop("expected_on_target_faced", 0.0)
            record["goals_prevented"] = round(
                expected * scale - record["goals_conceded"], 3)
        entry["history"].sort(key=lambda h: h["match_id"])
        entry["metrics"] = per_90(entry["history"])
        entry["expectation_scale"] = scale

    if progress:
        print(f"\n  Escala de expectativa: {scale:.3f} "
              f"(la poblacion la fija; 1.0 seria xG previo sin corregir)",
              file=sys.stderr)
    if unknown:
        print(f"\n  Tipos de evento no reconocidos: {dict(unknown)}",
              file=sys.stderr)
    if unlinked:
        print(f"  Tiros sin remate enlazado (contados, sin xG): {unlinked}",
              file=sys.stderr)
    return dict(keepers)


SOURCE = "statsbomb_wc2022"


def to_payload(keepers, min_matches=3) -> dict:
    """The goalkeepers as Kumu's ingest contract wants them.

    Position goes in as "Goalkeeper", the provider's own word, because
    PROVIDER_GROUP_OVERRIDE is keyed on the raw name and `rate_history`
    normalises it internally anyway. No index is supplied: the schema
    says it is derived, and it is normalised across the whole population,
    which one competition cannot see.
    """
    players = []
    for name, entry in sorted(keepers.items()):
        history = entry["history"]
        if len(history) < min_matches:
            continue
        players.append({
            # sha1, not hash(): Python randomises string hashing per
            # process, so the built-in would mint a new id on every run and
            # the ON CONFLICT update would insert 28 duplicates instead.
            "external_id": "sbgk_" + hashlib.sha1(
                name.strip().lower().encode("utf-8")).hexdigest()[:16],
            "name": name,
            "position": "Goalkeeper",
            "nationality": entry["team"],
            "current_team": entry["team"],
            "metrics": {"goalkeeping": entry["metrics"]},
            "performance_history": [
                {k: v for k, v in record.items() if k in MATCH_FIELDS}
                for record in history
            ],
        })
    return {"contract_version": "1.0", "source": SOURCE, "players": players}


MATCH_FIELDS = {
    "match_id", "minutes", "saves", "shots_on_target_faced",
    "goals_conceded", "goals_prevented", "claims", "sweeper_actions",
    "pass_completion",
}


def write(payload, org_id, i_mean_it) -> int:
    """Load into a tenant, normally the public reference population.

    The other loaders in this pipeline refuse the public organisation
    without `--i-mean-it`, because a client's players landing there would
    shift percentiles for people who never asked. This one is pointed at
    it on purpose - Kumu has no goalkeepers to compare against, which is
    the whole reason the position reported an unscaled index - so the
    flag is still required, and still has to be typed.
    """
    import os

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from app.schemas.ingest import IngestPayload, describe_capabilities
    from app.services import ingest_service

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Set DATABASE_URL first (source ~/.kumu_env).")

    db = sessionmaker(bind=create_engine(url))()
    public = db.execute(
        text("SELECT id, name FROM organizations WHERE slug = 'public'")
    ).fetchone()
    public_id = int(public[0]) if public else None

    if org_id is None:
        if public_id is None:
            raise SystemExit("No public organisation to load into.")
        org_id = public_id
    if org_id == public_id and not i_mean_it:
        raise SystemExit(
            "Organisation %d is the public reference population: every "
            "client's percentiles are computed against it. That is where "
            "these belong, but pass --i-mean-it to say so." % org_id
        )

    name = db.execute(text("SELECT name FROM organizations WHERE id = :i"),
                      {"i": org_id}).fetchone()
    if not name:
        raise SystemExit("No organisation with id %d." % org_id)
    print(f"Escribiendo en la organizacion {org_id}: {name[0]}")

    parsed = IngestPayload(**payload)
    capability = describe_capabilities(parsed)["capabilities"]
    print(f"  goalkeeper_rating: {capability['goalkeeper_rating']}")

    org_ids = [org_id] if public_id is None else sorted({org_id, public_id})
    result = ingest_service.ingest(db, parsed, org_id, org_ids)
    print(f"  escritos: {result.get('players_written')}")
    if result.get("players_skipped"):
        print(f"  descartados: {result['players_skipped']}")
    if result.get("positions_without_reference"):
        print("  sin poblacion de referencia: "
              f"{result['positions_without_reference']}")
    db.close()
    return int(result.get("players_written") or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--match", type=int, action="append", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--min-matches", type=int, default=3)
    parser.add_argument("--write", action="store_true",
                        help="Write to the database")
    parser.add_argument("--org", type=int, default=None,
                        help="Tenant to write into; the public one by default")
    parser.add_argument("--i-mean-it", action="store_true",
                        help="Confirm writing into the public population")
    args = parser.parse_args()

    keepers = derive(args.match)
    print(f"\nArqueros: {len(keepers)}")

    from app.core.scoring import match_rating, raw_index  # noqa: E402

    rated = []
    for name, entry in keepers.items():
        history = []
        for record in entry["history"]:
            rating = match_rating(record, "goalkeeper")
            if rating is not None:
                record["rating"] = round(rating, 2)
            history.append(record)
        index = raw_index(history)
        if index and len(history) >= args.min_matches:
            rated.append((name, entry["team"], len(history), index, entry["metrics"]))

    rated.sort(key=lambda r: -r[3]["value"])
    print(f"Con al menos {args.min_matches} partidos: {len(rated)}\n")
    print(f"{'arquero':26s} {'seleccion':14s} {'pj':>3s} {'indice':>7s} "
          f"{'par/90':>7s} {'%par':>6s} {'ge/90':>7s}")
    for name, team, played, index, metrics in rated:
        print(f"{name[:25]:26s} {str(team)[:13]:14s} {played:3d} "
              f"{index['value']:7.1f} {metrics.get('saves_per_90') or 0:7.2f} "
              f"{(metrics.get('save_percentage') or 0) * 100:5.0f}% "
              f"{metrics.get('goals_prevented_per_90') or 0:+7.3f}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(keepers, handle, indent=1, ensure_ascii=False)
        print(f"\n-> {args.out}")

    if not args.write:
        print("\nNada escrito. Pasa --write para cargar.")
        return 0

    payload = to_payload(keepers, args.min_matches)
    print(f"\nCargando {len(payload['players'])} arqueros...")
    write(payload, args.org, args.i_mean_it)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
