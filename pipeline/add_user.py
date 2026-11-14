"""
Kumü — add a user to an organisation that already exists
=========================================================

    python3 pipeline/add_user.py --org 23 --email tu@correo.cl

`/auth/signup` creates an organisation AND its first user together,
which is right for a club signing up and no use for an organisation the
pipeline created: signing up again would make a twenty-fourth
organisation next to the one holding the data. There was no other way
to put a login against an existing tenant, so a load like the A-League
one landed 101 players nobody could see.

The password is read from the terminal, never from the command line: an
argument lands in shell history and is visible in `ps` to anyone else on
the machine while the command runs.

Hashing goes through `app.core.security.hash_password`, the same bcrypt
call `/signup` uses, so a user made here logs in through the ordinary
endpoint with no special case.

Writing into the PUBLIC organisation needs `--i-mean-it`: a user there
has write access to the reference population every client's percentiles
are computed against.
"""

import argparse
import getpass
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "backend"))

MIN_PASSWORD = 8


def main() -> int:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from app.core import security
    from app.db import models

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", type=int, required=True,
                        help="Existing organisation id")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default=None, help="Full name, optional")
    parser.add_argument("--role", default="owner", choices=["owner", "member"])
    parser.add_argument("--i-mean-it", action="store_true",
                        help="Allow adding a user to the public organisation")
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Set DATABASE_URL first (source ~/.kumu_env).")

    engine = create_engine(url)
    db = sessionmaker(bind=engine)()

    org = db.execute(
        text("SELECT name, slug, kind FROM organizations WHERE id = :i"),
        {"i": args.org},
    ).fetchone()
    if not org:
        raise SystemExit("No organisation with id %d." % args.org)
    if org[2] == "public" and not args.i_mean_it:
        raise SystemExit(
            "Organisation %d is the public reference population. A user there "
            "can write into the set every client is measured against. Pass "
            "--i-mean-it if that is really what you want." % args.org
        )

    email = args.email.strip().lower()
    taken = db.execute(
        text("SELECT organization_id FROM users WHERE lower(email) = :e"),
        {"e": email},
    ).fetchone()
    if taken:
        raise SystemExit(
            "%s already has an account, in organisation %s. Emails are unique "
            "across Kumu, so this one cannot be reused." % (email, taken[0])
        )

    print(f"Organizacion {args.org}: {org[0]}  (slug {org[1]}, kind {org[2]})")
    print(f"Usuario nuevo: {email}  rol {args.role}")
    password = getpass.getpass("Contraseña: ")
    if len(password) < MIN_PASSWORD:
        raise SystemExit("La contraseña necesita al menos %d caracteres."
                         % MIN_PASSWORD)
    if password != getpass.getpass("Repitela: "):
        raise SystemExit("No coinciden. Nada escrito.")

    user = models.User(
        organization_id=args.org,
        email=email,
        password_hash=security.hash_password(password),
        full_name=args.name,
        role=args.role,
        is_active=True,
    )
    db.add(user)
    db.commit()

    # Prove it round-trips through the same check /auth/login performs,
    # rather than trusting that the write succeeded.
    stored = db.execute(
        text("SELECT id, password_hash FROM users WHERE lower(email) = :e"),
        {"e": email},
    ).fetchone()
    ok = security.verify_password(password, stored[1])
    print(f"\nCreado usuario {stored[0]} en la organizacion {args.org}.")
    print(f"Verificacion de login: {'ok' if ok else 'FALLO'}")
    visible = db.execute(
        text("SELECT count(*) FROM players WHERE organization_id = :i"),
        {"i": args.org},
    ).fetchone()[0]
    print(f"Jugadores que vera ademas de los publicos: {visible}")
    db.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
