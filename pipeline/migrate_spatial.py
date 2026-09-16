"""Room for the spatial profile on players and teams."""
import os

from sqlalchemy import create_engine, text


def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Set DATABASE_URL first.")
    engine = create_engine(url)
    with engine.begin() as conn:
        for tabla in ("players", "teams"):
            conn.execute(text(
                f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS spatial_profile JSON"
            ))
            n = conn.execute(text(
                f"SELECT count(*) FROM {tabla} WHERE spatial_profile IS NOT NULL"
            )).scalar()
            print(f"  {tabla}: columna lista, {n} con perfil")


if __name__ == "__main__":
    main()
