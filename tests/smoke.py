"""Pre-demo battery: what manual exploration found, run every time.

A single afternoon of poking at the app with real client data turned up five
faults, two of them isolation leaks, in code that had already been audited. The
faults shared a shape — incomplete data, authenticated sessions, access across
tenants — so those are what this exercises.

It creates two throwaway client organisations, because every leak found so far
was "an anonymous visitor sees a client's data", and nobody had checked the case
that matters commercially: client A must not see client B.
"""
import sys
import time
import uuid

sys.path.insert(0, "backend")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

c = TestClient(app)
FALLOS = []
PASOS = []


def check(nombre, condicion, detalle=""):
    (PASOS if condicion else FALLOS).append(nombre)
    marca = "ok  " if condicion else "FALLA"
    extra = "" if condicion else f" — {detalle}"
    print(f"  {marca} {nombre}{extra}")


def nuevo_cliente(etiqueta):
    email = f"smoke-{etiqueta}-{uuid.uuid4().hex[:8]}@ejemplo.com"
    r = c.post("/api/v1/auth/signup", json={
        "organization_name": f"Smoke {etiqueta} {uuid.uuid4().hex[:6]}",
        "email": email, "password": "contrasena-de-prueba-123",
    })
    if r.status_code != 201:
        raise SystemExit(f"no pude crear {etiqueta}: {r.status_code} {r.text[:200]}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def payload(etiqueta, completo=True):
    """A squad with one fully described player and, optionally, a bare one."""
    historial = [
        {"match_id": f"m{i}", "minutes": 90, "pass_completion": 0.8 + i * 0.01,
         "progressive_passes": 4 + i, "key_passes": 1, "tackles": 2, "goals": i % 2}
        for i in range(5)
    ]
    jugadores = [{
        "external_id": f"{etiqueta}-full", "name": f"Completo {etiqueta}",
        "position": "CM", "age": 25, "market_value": 800000, "nationality": "Chile",
        "metrics": {"passing": {"completion_rate": 0.85,
                                "progressive_passes_per_90": 5.0},
                    "defensive": {"tackles_per_90": 2.0}},
        "performance_history": historial,
    }]
    if not completo:
        # Every field the contract lets a client omit, omitted at once.
        jugadores.append({
            "external_id": f"{etiqueta}-thin", "name": f"Minimo {etiqueta}",
            "position": "ST",
            "metrics": {"shooting": {"goals_per_90": 0.4}},
            "performance_history": historial[:3],
        })
    return {
        "source": f"smoke-{etiqueta}",
        "club": {"external_id": f"{etiqueta}-club", "name": f"Club {etiqueta}",
                 "league": "Primera Division de Chile", "country": "Chile",
                 "budget": 1500000, "possession": 0.5, "pressing_intensity": 0.55,
                 "squad": [j["external_id"] for j in jugadores]},
        "players": jugadores,
    }


def ids_de(h, parcial):
    return [p["id"] for p in c.get("/api/v1/players/?limit=500", headers=h).json()
            if parcial in p["name"]]


def club_de(h, parcial):
    ids = [t["id"] for t in c.get("/api/v1/teams/?limit=200", headers=h).json()
           if parcial in t["name"]]
    return ids[0] if ids else None


def main():
    t0 = time.time()

    print("\n== preparacion ==")
    hA, hB = nuevo_cliente("A"), nuevo_cliente("B")
    rA = c.post("/api/v1/ingest/players", headers=hA, json=payload("A", completo=False))
    rB = c.post("/api/v1/ingest/players", headers=hB, json=payload("B"))
    check("carga del cliente A", rA.status_code == 200, rA.text[:120])
    check("carga del cliente B", rB.status_code == 200, rB.text[:120])

    print("\n== aislamiento entre clientes ==")
    nombresA = {p["name"] for p in c.get("/api/v1/players/?limit=500", headers=hA).json()}
    nombresB = {p["name"] for p in c.get("/api/v1/players/?limit=500", headers=hB).json()}
    check("A ve lo suyo", "Completo A" in nombresA)
    check("B ve lo suyo", "Completo B" in nombresB)
    check("A NO ve jugadores de B", "Completo B" not in nombresA)
    check("B NO ve jugadores de A", "Completo A" not in nombresB)
    check("A NO ve el club de B", club_de(hA, "Club B") is None)
    pidA = ids_de(hA, "Completo A")[0]
    check("B NO lee un jugador de A por id",
          c.get(f"/api/v1/players/{pidA}", headers=hB).status_code == 404)

    print("\n== tolerancia a datos incompletos ==")
    clubA = club_de(hA, "Club A")
    finos = ids_de(hA, "Minimo A")
    check("el jugador minimo se cargo", bool(finos))
    if finos and clubA:
        pid = finos[0]
        check("detalle del jugador minimo",
              c.get(f"/api/v1/players/{pid}", headers=hA).status_code == 200)
        rm = c.post("/api/v1/matches/calculate", headers=hA,
                    json={"player_id": str(pid), "team_ids": [], "min_score": 0})
        check("matching con jugador minimo", rm.status_code == 200, rm.text[:120])
        rr = c.post("/api/v1/reports/generate", headers=hA,
                    json={"player_id": str(pid), "team_id": str(clubA)})
        check("reporte con jugador minimo", rr.status_code == 200, rr.text[:120])
        if rr.status_code == 200:
            d = rr.json()
            roi = d["market_analysis"]["roi_analysis"]["roi_percentage"]
            check("el ROI no se dispara", roi < 1000, f"ROI {roi:.0f}%")
            hallazgos = d["executive_summary"]["key_findings"]
            check("declara la edad ausente",
                  any("not available" in f for f in hallazgos if "Age" in f))
            if rm.status_code == 200 and rm.json():
                a = rm.json()[0]["offer"]["recommended"]
                b = d["market_analysis"]["current_market_value"]
                check("matching y reporte coinciden en el valor",
                      abs(a - b) < max(1.0, b * 0.01), f"{a} vs {b}")

    print("\n== sesion ==")
    check("anonimo lee la referencia publica",
          len(c.get("/api/v1/players/?limit=20").json()) > 0)
    check("token invalido cae a anonimo sin romper",
          c.get("/api/v1/auth/me",
                headers={"Authorization": "Bearer basura"}).json()
          .get("authenticated") is False)
    check("anonimo no puede escribir",
          c.post("/api/v1/ingest/players", json=payload("X")).status_code == 401)

    print(f"\n== resumen == {len(PASOS)} ok, {len(FALLOS)} fallas, {time.time()-t0:.1f}s")
    for f in FALLOS:
        print(f"  FALLA: {f}")
    return 1 if FALLOS else 0


if __name__ == "__main__":
    sys.exit(main())
