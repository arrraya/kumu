"""
Kumü — generate every report against the real database and check it
====================================================================

    source ~/.kumu_env
    python3 pipeline/verify_reports.py              # cada inquilino
    python3 pipeline/verify_reports.py --org 23     # sólo ese
    python3 pipeline/verify_reports.py --limit 20   # una muestra
    python3 pipeline/verify_reports.py --player 2533 --team 188

Read-only. It writes nothing and opens one session, which it closes.

It pairs the way the endpoint pairs: a tenant's players against the clubs
that tenant can read, which is its own plus the public organisation's.
Crossing every player with every club asks for reports nobody can
request - the first run produced 27,783 pairs across six tenants, most of
them combinations `readable_org_ids` would refuse.

WHY THIS EXISTS
---------------
Two breakages reached production in one afternoon, and both were verified
beforehand. The SQL was read instead of executed, because `_query_db`
fails softly with no database and all 101 reports generated cleanly
without touching one. The budget was exercised against a club invented
for the test, with a budget of a million, while the endpoint's own eight
A-League clubs carry none.

Reading cannot catch either. A fixture cannot catch the second. What
catches both is generating the real reports from the real rows and
asserting things that cannot be true of any of them.

WHAT IT ASSERTS
---------------
Not that the figures are right - nothing here knows what right is. Only
that no report claims a population it was not measured against, and that
no absence is reported as a favourable number. Those are the two shapes
every defect this month has taken.
"""

import argparse
import os
import re
import signal
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "backend"))


# Set by Ctrl-C, read between reports.
#
# psycopg2 blocks inside C while it waits on Railway, and at four seconds
# a report that is most of the time: the interrupt is not delivered until
# the query returns, so the first Ctrl-C appeared to do nothing and the
# run could only be killed from another terminal. Checking a flag at the
# report boundary stops it at the next one, and - the part that matters -
# still prints what it found. A verification that must run to the end to
# say anything is a verification nobody runs.
INTERRUMPIDO = False


def _detener(signum, frame):  # noqa: ARG001
    global INTERRUMPIDO
    if INTERRUMPIDO:
        raise KeyboardInterrupt  # segundo Ctrl-C: salir ya
    INTERRUMPIDO = True
    print("\n[!] cortando al terminar este reporte…", file=sys.stderr)


def spread(rows, n, key):
    """N rows covering as many distinct values of `key` as possible.

    Taking the first N instead would have sampled whatever the table
    happened to return first: all forwards, or only the clubs that carry a
    budget. These checks are about shape, so the sample has to span the
    shapes rather than the rows.
    """
    if n >= len(rows):
        return rows
    grupos = {}
    for row in rows:
        grupos.setdefault(key(row), []).append(row)
    salida, orden = [], sorted(grupos, key=lambda k: (k is None, str(k)))
    while len(salida) < n:
        movido = False
        for k in orden:
            if grupos[k] and len(salida) < n:
                salida.append(grupos[k].pop(0))
                movido = True
        if not movido:
            break
    return salida


def leagues_in_play(teams) -> set:
    """Every league name any club carries, so a claim can be caught."""
    return {t.league for t in teams if getattr(t, "league", None)}


def check(report, player, team, leagues) -> list:
    """What cannot be true of a finished report. Returns the failures."""
    bad = []

    summary = report.get("executive_summary") or {}
    said = summary.get("executive_statement") or ""

    # 1. A percentile belongs to the population that produced it. The peer
    #    ranking has no league filter, so naming any league is a claim the
    #    query cannot support - and the one it used to name was the
    #    assessing club's.
    for league in leagues:
        if league and league in said:
            bad.append("la frase ejecutiva nombra la liga %r: %s"
                       % (league, said.strip()))

    # 2. A percentile is stated only where one was established.
    pct = summary.get("overall_percentile")
    if pct is None and "percentile" in said.lower():
        if "No percentile is stated" not in said:
            bad.append("no hay percentil pero la frase habla de uno: %s"
                       % said.strip())

    # 3. A metric with no benchmark keeps its value and loses its verdict.
    stats = report.get("statistical_overview") or {}
    for category, metrics in (stats.get("position_specific_analysis") or {}).items():
        for metric, analysis in metrics.items():
            if analysis.get("percentile") is None and analysis.get("performance"):
                bad.append("%s.%s sin percentil pero con veredicto %r"
                           % (category, metric, analysis["performance"]))

    # 4. An absence is never the favourable answer. A sub-risk that scored
    #    zero has to have had something to score.
    risks = (report.get("risk_assessment") or {}).get("risk_factors") or {}
    for name, rf in risks.items():
        if rf.get("score") == 0 and not rf.get("basis"):
            bad.append("%s en 0 sin decir sobre qué se midió" % name)
        if rf.get("score") is None and rf.get("level"):
            bad.append("%s sin puntaje pero con nivel %r" % (name, rf["level"]))

    # 5. A club with no budget is not a club that cannot pay.
    if not getattr(team, "budget", None):
        fin = risks.get("financial_risk") or {}
        if fin.get("score") is not None:
            bad.append("riesgo financiero %s para un club sin presupuesto"
                       % fin["score"])

    # 6. Money on the page always comes from somewhere.
    market = report.get("market_analysis") or {}
    contract = market.get("contract_recommendations") or {}
    if not getattr(team, "budget", None) and contract.get("base_wage"):
        if "not adjusted" not in (contract.get("basis") or "").lower():
            bad.append("sueldo sin decir que no está ajustado al club")

    return bad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None,
                        help="Sólo N jugadores, repartidos entre posiciones")
    parser.add_argument("--clubs", type=int, default=None,
                        help="Sólo N clubes, cubriendo con y sin presupuesto")
    parser.add_argument("--player", type=int, action="append", default=None)
    parser.add_argument("--team", type=int, action="append", default=None)
    parser.add_argument("--org", type=int, action="append", default=None,
                        help="Organizaciones legibles; por defecto todas")
    args = parser.parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("Falta DATABASE_URL. Corre `source ~/.kumu_env` primero.",
              file=sys.stderr)
        return 2

    from app.db import models
    from app.db.database import SessionLocal
    from app.services import player_service, team_service
    from app.services.scouting_report_generator import ScoutingReportGenerator

    db = SessionLocal()
    try:
        # Pair the way the endpoint pairs. `readable_org_ids` gives a user
        # their own organisation plus the public one, never two tenants at
        # once, so crossing every player with every club asks for reports
        # nobody can request: the first run of this script produced 27,783
        # pairs across 441 players and 63 clubs, most of them combinations
        # the API would refuse.
        publica = db.query(models.Organization).filter(
            models.Organization.slug == "public").first()
        publica_id = publica.id if publica else None

        orgs = args.org or [
            o.id for o in db.query(models.Organization).all()
            if o.id != publica_id
        ] or [publica_id]

        lotes = []
        for org_id in orgs:
            visibles = [i for i in (org_id, publica_id) if i is not None]
            players = (db.query(models.Player)
                       .filter(models.Player.organization_id == org_id).all())
            teams = (db.query(models.Team)
                     .filter(models.Team.organization_id.in_(visibles)).all())
            if args.player:
                players = [p for p in players if p.id in set(args.player)]
            if args.team:
                teams = [t for t in teams if t.id in set(args.team)]
            if args.limit:
                players = spread(players, args.limit,
                                 lambda p: getattr(p, "position", None))
            if args.clubs:
                # Both budget states on purpose. These are defects of shape,
                # not of player: one club that carries a budget and one that
                # does not exercise every branch the whole list would.
                teams = spread(teams, args.clubs, lambda t: bool(t.budget))
            if players and teams:
                lotes.append((org_id, visibles, players, teams))

        if not lotes:
            print("Nada que verificar con ese alcance.", file=sys.stderr)
            return 2

        total = sum(len(p) * len(t) for _, _, p, t in lotes)
        print("[*] %d reportes en %d organizacion(es)" % (total, len(lotes)))
        for org_id, _, players, teams in lotes:
            sin = [t.name for t in teams if not t.budget]
            print("    org %-4s %3d jugadores x %2d clubes | sin presupuesto: %s"
                  % (org_id, len(players), len(teams),
                     ", ".join(sin[:6]) + ("…" if len(sin) > 6 else "")
                     or "ninguno"))
        print()

        signal.signal(signal.SIGINT, _detener)

        g = ScoutingReportGenerator()
        fallos, rotos, hechos = [], [], 0
        comenzado = time.time()

        for org_id, visibles, players, teams in lotes:
            if INTERRUMPIDO:
                break
            leagues = leagues_in_play(teams)
            for player in players:
                if INTERRUMPIDO:
                    break
                player_data = g.build_player_data(player)
                for team in teams:
                    if INTERRUMPIDO:
                        break
                    team_data = {
                        "id": team.id,
                        "name": team.name,
                        "league": getattr(team, "league", None),
                        "country": getattr(team, "country", None),
                        # Exactly what the endpoint passes, absence included.
                        # A fixture with a budget of a million is what let
                        # the last one through.
                        "budget": getattr(team, "budget", None),
                        "formation": getattr(team, "formation", None),
                        "playing_style": getattr(team, "playing_style", None) or {},
                        "requirements": getattr(team, "requirements", None) or {},
                        "spatial_profile": getattr(team, "spatial_profile", None) or {},
                        "expected_index": getattr(team, "expected_index", None),
                    }
                    try:
                        report = g.generate_full_report(
                            player_data, team_data, visibles)
                    except Exception as exc:  # noqa: BLE001
                        rotos.append((player.name, team.name, repr(exc),
                                      traceback.format_exc(limit=3)))
                        continue
                    hechos += 1
                    for problema in check(report, player, team, leagues):
                        fallos.append((player.name, team.name, problema))

                transcurrido = time.time() - comenzado
                ritmo = hechos / transcurrido if transcurrido else 0
                print("  %-26s %5d/%d  %4.0f/s  faltan ~%dm"
                      % (player.name[:26], hechos, total, ritmo,
                         (total - hechos) / ritmo / 60 if ritmo else 0),
                      file=sys.stderr)

        print()
        if INTERRUMPIDO:
            print("cortado a mano: %d de %d reportes" % (hechos, total))
        print("generados: %d" % hechos)
        print("rotos:     %d" % len(rotos))
        print("objeciones: %d" % len(fallos))

        for name, club, exc, tb in rotos[:5]:
            print("\n  ROTO  %s / %s\n    %s" % (name, club, exc))
            print("    " + tb.strip().replace("\n", "\n    "))

        vistos = set()
        for name, club, problema in fallos:
            clave = re.sub(r"\d+", "N", problema)[:70]
            if clave in vistos:
                continue
            vistos.add(clave)
            print("\n  %s / %s\n    %s" % (name, club, problema))
        if len(vistos) < len(fallos):
            print("\n  (%d objeciones en total, %d formas distintas)"
                  % (len(fallos), len(vistos)))

        return 1 if (rotos or fallos) else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
