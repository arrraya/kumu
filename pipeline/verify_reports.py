"""
Kumü — generate every report against the real database and check it
====================================================================

    source ~/.kumu_env
    python3 pipeline/verify_reports.py              # todos contra todos
    python3 pipeline/verify_reports.py --limit 20   # una muestra
    python3 pipeline/verify_reports.py --player 2533 --team 188

Read-only. It writes nothing and opens one session, which it closes.

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
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "backend"))


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
                        help="Sólo los primeros N jugadores")
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
        org_ids = args.org or [o.id for o in db.query(models.Organization).all()]

        teams = db.query(models.Team).all()
        if args.team:
            teams = [t for t in teams if t.id in set(args.team)]
        players = db.query(models.Player).all()
        if args.player:
            players = [p for p in players if p.id in set(args.player)]
        if args.limit:
            players = players[:args.limit]

        leagues = leagues_in_play(teams)
        sin_presupuesto = [t.name for t in teams if not t.budget]

        print("[*] %d jugadores x %d clubes = %d reportes"
              % (len(players), len(teams), len(players) * len(teams)))
        print("[*] ligas en juego: %s" % ", ".join(sorted(leagues)))
        print("[*] clubes sin presupuesto: %s"
              % (", ".join(sin_presupuesto) or "ninguno"))
        print()

        g = ScoutingReportGenerator()
        fallos, rotos, hechos = [], [], 0

        for player in players:
            player_data = g.build_player_data(player)
            for team in teams:
                team_data = {
                    "id": team.id,
                    "name": team.name,
                    "league": getattr(team, "league", None),
                    "country": getattr(team, "country", None),
                    # Exactly what the endpoint passes, absence included.
                    # A fixture with a budget of a million is what let the
                    # last one through.
                    "budget": getattr(team, "budget", None),
                    "formation": getattr(team, "formation", None),
                    "playing_style": getattr(team, "playing_style", None) or {},
                    "requirements": getattr(team, "requirements", None) or {},
                    "spatial_profile": getattr(team, "spatial_profile", None) or {},
                    "expected_index": getattr(team, "expected_index", None),
                }
                try:
                    report = g.generate_full_report(player_data, team_data, org_ids)
                except Exception as exc:  # noqa: BLE001
                    rotos.append((player.name, team.name, repr(exc),
                                  traceback.format_exc(limit=3)))
                    continue
                hechos += 1
                for problema in check(report, player, team, leagues):
                    fallos.append((player.name, team.name, problema))

            if len(players) > 5:
                print("  %-28s %d/%d" % (player.name[:28], hechos,
                                         len(players) * len(teams)),
                      file=sys.stderr)

        print()
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
