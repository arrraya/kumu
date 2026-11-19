"""
Kumü — what the database actually holds, and what a report costs
=================================================================

    source ~/.kumu_env
    python3 pipeline/inspect_shape.py

Read-only. Prints three things and changes nothing.

1. WHERE THE FOUR SECONDS GO
   A report takes about four seconds, and that is latency to Railway, not
   arithmetic. The endpoint pays the same once per request a user makes.
   Many small queries are joined; few slow ones are an index. The
   difference is counted, not guessed, so this times every query one
   report makes and groups them by the statement that issued them.

2. WHAT THE LEAGUE NAMES ARE
   A league called literally `League` turned up beside Bundesliga and
   Eredivisie, with `International`, and `Primera Division` living
   alongside `Primera Division de Chile`. These strings decide which
   reference population a player is measured against, so two spellings of
   one competition are two populations.

3. WHICH TEAMS ARE NOT CLUBS
   `team_type` already distinguishes them. This says whether the column
   is actually populated, because a rule nothing fills is not a rule.
"""

import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "backend"))

BAR = "─" * 62


def seccion(titulo):
    print("\n" + BAR)
    print(titulo)
    print(BAR)


def perfilar(db, models, org_ids, player_id=None):
    """Time every query one report makes, grouped by statement."""
    from sqlalchemy import event

    from app.db.database import engine
    from app.services.scouting_report_generator import ScoutingReportGenerator

    gastos = defaultdict(lambda: {"n": 0, "s": 0.0})
    arranque = {}

    def antes(conn, cursor, statement, params, context, many):  # noqa: ARG001
        arranque[id(context)] = time.perf_counter()

    def despues(conn, cursor, statement, params, context, many):  # noqa: ARG001
        inicio = arranque.pop(id(context), None)
        if inicio is None:
            return
        clave = " ".join(statement.split())[:88]
        gastos[clave]["n"] += 1
        gastos[clave]["s"] += time.perf_counter() - inicio

    consulta = (db.query(models.Player)
                .filter(models.Player.organization_id.in_(org_ids))
                .filter(models.Player.performance_index.isnot(None)))
    if player_id:
        consulta = consulta.filter(models.Player.id == player_id)
    else:
        # Otherwise it takes whatever the table returns first, which last
        # time was "Volante Demo" from the test tenant: a profile of a
        # player nobody will ever ask for.
        consulta = consulta.filter(models.Player.organization_id != 2)
    player = consulta.first()
    team = (db.query(models.Team)
            .filter(models.Team.organization_id.in_(org_ids))
            .filter((models.Team.team_type == "club")
                    | (models.Team.team_type.is_(None)))
            .first())
    if not player or not team:
        print("  No hay jugador o club en ese alcance.")
        return

    g = ScoutingReportGenerator()
    player_data = g.build_player_data(player)
    team_data = {
        "id": team.id, "name": team.name, "league": team.league,
        "country": team.country, "budget": team.budget,
        "formation": team.formation,
        "playing_style": team.playing_style or {},
        "requirements": team.requirements or {},
        "spatial_profile": team.spatial_profile or {},
    }

    import cProfile
    import pstats

    perfil = cProfile.Profile()
    event.listen(engine, "before_cursor_execute", antes)
    event.listen(engine, "after_cursor_execute", despues)
    comenzado = time.perf_counter()
    try:
        perfil.enable()
        g.generate_full_report(player_data, team_data, org_ids)
        perfil.disable()
    finally:
        total = time.perf_counter() - comenzado
        event.remove(engine, "before_cursor_execute", antes)
        event.remove(engine, "after_cursor_execute", despues)

    consultas = sum(v["n"] for v in gastos.values())
    en_base = sum(v["s"] for v in gastos.values())
    print("  jugador: %s | club: %s" % (player.name, team.name))
    print("  reporte completo: %.2f s" % total)
    print("  consultas: %d, %.2f s en la base (%.0f%% del total)"
          % (consultas, en_base, en_base / total * 100 if total else 0))
    print("  fuera de la base: %.2f s" % (total - en_base))
    print()
    print("  %-5s %7s %7s  %s" % ("veces", "total", "c/u", "consulta"))
    for clave, v in sorted(gastos.items(), key=lambda kv: -kv[1]["s"])[:12]:
        print("  %5d %6.2fs %6.3fs  %s" % (v["n"], v["s"], v["s"] / v["n"], clave))

    # The part the deployed server actually pays. Its database sits beside
    # it in Railway, where a round trip is sub-millisecond, so the seconds
    # measured above are this laptop's distance to US West and not the
    # endpoint's cost. Whatever is left over is Python, and that it does pay
    # once per report a user asks for.
    print()
    print("  --- fuera de la base: %.2f s, que es lo que paga producción ---"
          % (total - en_base))
    stats = pstats.Stats(perfil)
    stats.sort_stats("cumulative")
    propio = [
        (func, st) for func, st in stats.stats.items()
        if ("/app/" in func[0] or "/backend/" in func[0])
    ]
    propio.sort(key=lambda kv: -kv[1][3])  # tiempo acumulado
    print("  %8s %8s %6s  %s" % ("acum", "propio", "veces", "función"))
    for (archivo, linea, nombre), (cc, nc, tt, ct, _) in propio[:12]:
        corto = archivo.split("/app/")[-1] if "/app/" in archivo else archivo
        print("  %7.3fs %7.3fs %6d  %s:%d %s"
              % (ct, tt, nc, corto, linea, nombre))

    repetidas = [(k, v) for k, v in gastos.items() if v["n"] > 1]
    if repetidas:
        ahorro = sum(v["s"] - v["s"] / v["n"] for _, v in repetidas)
        print()
        print("  %d consultas idénticas se repiten; emitirlas una vez "
              "ahorraría ~%.2f s" % (sum(v["n"] for _, v in repetidas), ahorro))


def ligas(db, models):
    filas = defaultdict(lambda: {"equipos": 0, "clubes": 0, "jugadores": 0})
    for t in db.query(models.Team).all():
        nombre = t.league or "(sin liga)"
        filas[nombre]["equipos"] += 1
        if (t.team_type or "club") == "club":
            filas[nombre]["clubes"] += 1
    for p in db.query(models.Player).all():
        nombre = getattr(p, "current_league", None) or "(sin liga)"
        filas[nombre]["jugadores"] += 1

    print("  %-34s %7s %7s %10s" % ("liga", "equipos", "clubes", "jugadores"))
    for nombre in sorted(filas):
        v = filas[nombre]
        print("  %-34s %7d %7d %10d"
              % (nombre[:34], v["equipos"], v["clubes"], v["jugadores"]))

    # Two spellings of one competition are two reference populations.
    nombres = sorted(filas)
    sospechosas = []
    for i, a in enumerate(nombres):
        for b in nombres[i + 1:]:
            ca, cb = a.casefold(), b.casefold()
            if ca != cb and (ca in cb or cb in ca):
                sospechosas.append((a, b))
    if sospechosas:
        print("\n  Una contiene a la otra — probablemente la misma competencia:")
        for a, b in sospechosas:
            print("    %r  /  %r" % (a, b))

    genericas = [n for n in nombres
                 if n.casefold() in {"league", "international", "(sin liga)",
                                     "unknown", "n/a"}]
    if genericas:
        print("\n  Nombres que no identifican una competencia: %s"
              % ", ".join(repr(n) for n in genericas))


def tipos(db, models):
    cuenta = defaultdict(int)
    sin_tipo = []
    for t in db.query(models.Team).all():
        clave = t.team_type or "(nulo)"
        cuenta[clave] += 1
        if not t.team_type:
            sin_tipo.append(t.name)
    for clave in sorted(cuenta):
        print("  %-12s %d" % (clave, cuenta[clave]))
    if sin_tipo:
        print("\n  Sin team_type (%d), tratados como club: %s%s"
              % (len(sin_tipo), ", ".join(sin_tipo[:10]),
                 "…" if len(sin_tipo) > 10 else ""))

    nacionales_con_presupuesto = [
        t.name for t in db.query(models.Team).all()
        if (t.team_type == "national") and t.budget
    ]
    if nacionales_con_presupuesto:
        print("\n  Selecciones con presupuesto (no debería haber): %s"
              % ", ".join(nacionales_con_presupuesto))


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--player", type=int, default=None,
                        help="Perfilar este jugador; por defecto el primero "
                             "que no sea del inquilino de prueba")
    args = parser.parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("Falta DATABASE_URL. Corre `source ~/.kumu_env` primero.",
              file=sys.stderr)
        return 2

    from app.db import models
    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        org_ids = [o.id for o in db.query(models.Organization).all()]

        seccion("1. DÓNDE SE VAN LOS CUATRO SEGUNDOS")
        perfilar(db, models, org_ids, args.player)

        seccion("2. NOMBRES DE LIGA")
        ligas(db, models)

        seccion("3. CLUBES Y SELECCIONES")
        tipos(db, models)

        print()
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
