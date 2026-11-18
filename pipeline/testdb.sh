#!/usr/bin/env bash
#
# Kumü — a throwaway Postgres for the test suite
# ===============================================
#
#     bash pipeline/testdb.sh          # arrancar / crear
#     bash pipeline/testdb.sh status   # ver qué hay
#     bash pipeline/testdb.sh stop     # apagar (Docker)
#     bash pipeline/testdb.sh destroy  # borrar del todo
#
# Prints the one line to paste into your shell when it is ready. Installs
# nothing: it uses Docker or a Homebrew Postgres if one is already there,
# and otherwise says what to install and stops.
#
# The database is called kumu_test on purpose. tests/dbfixture.py refuses
# to create or drop tables in a database whose name does not contain
# "test", and refuses outright if the URL matches DATABASE_URL.

set -u

PUERTO="${KUMU_TEST_PORT:-55432}"
BASE="kumu_test"
CONTENEDOR="kumu-test-db"
IMAGEN="postgres:16-alpine"
CLAVE="kumu"

azul()  { printf '\033[1m%s\033[0m\n' "$*"; }
gris()  { printf '  %s\n' "$*"; }

url_docker() { echo "postgresql://postgres:${CLAVE}@localhost:${PUERTO}/${BASE}"; }
url_brew()   { echo "postgresql://localhost:5432/${BASE}"; }

hay_docker() { command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; }
hay_brew_pg() { command -v pg_ctl >/dev/null 2>&1 && command -v createdb >/dev/null 2>&1; }

# ------------------------------------------------------------------ estado

estado() {
  azul "Qué hay en esta máquina"
  if command -v docker >/dev/null 2>&1; then
    if docker info >/dev/null 2>&1; then
      gris "docker: instalado y corriendo"
      if docker ps -a --format '{{.Names}}' | grep -qx "$CONTENEDOR"; then
        local vivo
        vivo=$(docker inspect -f '{{.State.Running}}' "$CONTENEDOR" 2>/dev/null)
        gris "contenedor $CONTENEDOR: existe (corriendo=$vivo)"
      else
        gris "contenedor $CONTENEDOR: no existe todavía"
      fi
    else
      gris "docker: instalado pero el demonio no responde (abre Docker Desktop)"
    fi
  else
    gris "docker: no instalado"
  fi

  if hay_brew_pg; then
    gris "postgres local: $(command -v postgres || command -v pg_ctl)"
    if pg_isready -q 2>/dev/null; then
      gris "postgres local: aceptando conexiones"
    else
      gris "postgres local: instalado pero no corriendo"
    fi
  else
    gris "postgres local: no instalado"
  fi
}

# ------------------------------------------------------------------ arrancar

con_docker() {
  if docker ps -a --format '{{.Names}}' | grep -qx "$CONTENEDOR"; then
    docker start "$CONTENEDOR" >/dev/null 2>&1 || true
  else
    azul "Creando el contenedor $CONTENEDOR"
    docker run -d --name "$CONTENEDOR" \
      -e POSTGRES_PASSWORD="$CLAVE" \
      -e POSTGRES_DB="$BASE" \
      -p "${PUERTO}:5432" \
      "$IMAGEN" >/dev/null || return 1
  fi

  printf '  esperando a que acepte conexiones'
  for _ in $(seq 1 40); do
    if docker exec "$CONTENEDOR" pg_isready -U postgres -q 2>/dev/null; then
      printf ' listo\n'
      # Idempotente: el contenedor ya la crea al nacer, pero no si existía
      # con otro POSTGRES_DB.
      docker exec "$CONTENEDOR" psql -U postgres -tAc \
        "SELECT 1 FROM pg_database WHERE datname='${BASE}'" 2>/dev/null \
        | grep -q 1 || docker exec "$CONTENEDOR" createdb -U postgres "$BASE"
      return 0
    fi
    printf '.'
    sleep 1
  done
  printf '\n'
  return 1
}

con_brew() {
  pg_isready -q 2>/dev/null || {
    azul "Postgres está instalado pero no corriendo"
    gris "brew services start postgresql@16"
    return 1
  }
  psql -lqt 2>/dev/null | cut -d\| -f1 | grep -qw "$BASE" || createdb "$BASE"
  return 0
}

arrancar() {
  if hay_docker; then
    con_docker && { listo "$(url_docker)"; return 0; }
    azul "Docker está pero no pudo levantar la base."
    return 1
  fi
  if hay_brew_pg; then
    con_brew && { listo "$(url_brew)"; return 0; }
    return 1
  fi

  azul "No hay ni Docker ni Postgres en esta máquina."
  echo
  gris "Docker Desktop (una sola instalación, nada más que mantener):"
  gris "    https://www.docker.com/products/docker-desktop/"
  echo
  gris "o Postgres con Homebrew:"
  gris "    brew install postgresql@16 && brew services start postgresql@16"
  echo
  gris "Después vuelve a correr: bash pipeline/testdb.sh"
  return 1
}

listo() {
  local url="$1"
  echo
  azul "Lista. Pega esto en tu terminal:"
  echo
  echo "    export KUMU_TEST_DATABASE_URL='${url}'"
  echo
  gris "y después:"
  gris "    python3 tests/test_queries.py"
  echo
  gris "Para dejarlo fijo, agrégalo a ~/.kumu_env — es una base desechable,"
  gris "sin datos reales, así que no es un secreto."
}

# ------------------------------------------------------------------ apagar

case "${1:-start}" in
  status)  estado ;;
  stop)
    hay_docker && docker stop "$CONTENEDOR" >/dev/null 2>&1 && \
      azul "Contenedor detenido." || azul "Nada que detener."
    ;;
  destroy)
    if hay_docker && docker ps -a --format '{{.Names}}' | grep -qx "$CONTENEDOR"; then
      docker rm -f "$CONTENEDOR" >/dev/null && azul "Contenedor borrado."
    elif hay_brew_pg; then
      dropdb --if-exists "$BASE" && azul "Base ${BASE} borrada."
    else
      azul "Nada que borrar."
    fi
    ;;
  start)   estado; echo; arrancar ;;
  *)       echo "uso: bash pipeline/testdb.sh [start|status|stop|destroy]" ;;
esac
