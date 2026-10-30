"""Idempotent startup: create tables, seed demo data if the database is empty
(otherwise move the demo order dates up to today), and build the Chroma index if it is empty. Used by the Docker entrypoint."""
import time

from sqlalchemy import func, select, text

from app.db import SessionLocal, engine, init_db


def wait_for_db(attempts: int = 30, delay: float = 2.0) -> None:
    for i in range(attempts):
        try:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            return
        except Exception as e:  # pragma: no cover - timing dependent
            print(f"waiting for database ({i + 1}/{attempts}): {type(e).__name__}")
            time.sleep(delay)
    raise SystemExit("database not reachable")


def main() -> None:
    from app.models import User
    from app.rag.ingest import get_collection, ingest
    from app.seed import refresh_demo_dates, seed

    wait_for_db()
    init_db()
    with SessionLocal() as db:
        users = db.scalar(select(func.count(User.id)))
    if users == 0:
        print("seeded:", seed(drop=False))
    else:
        print(f"database already has {users} users; not reseeding")
        print(f"demo order dates shifted by {refresh_demo_dates()} days")
    if get_collection().count() == 0:
        print("ingested:", ingest())
    else:
        print("vector index present; not re-ingesting")


if __name__ == "__main__":
    main()
