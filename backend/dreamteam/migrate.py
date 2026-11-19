import os
from pathlib import Path

import psycopg

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def migrate(db):
    db.execute("SELECT pg_advisory_xact_lock(70112894)")
    db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY)")
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if not db.execute("SELECT 1 FROM schema_migrations WHERE name = %s", (path.name,)).fetchone():
            db.execute(path.read_text(encoding="utf-8"))
            db.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))


if __name__ == "__main__":
    with psycopg.connect(os.environ["DREAMTEAM_DATABASE_URL"]) as connection:
        migrate(connection)
