import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import create_async_engine

from tennis_match_api.config import get_settings
from tennis_match_api.db import connect_migrator

_API_ROOT = Path(__file__).resolve().parents[3]


async def _upgrade() -> None:
    engine = create_async_engine(
        "mysql+asyncmy://",
        async_creator=connect_migrator,
        poolclass=pool.NullPool,
    )
    async with engine.connect() as connection:
        locked = (await connection.execute(text("SELECT GET_LOCK('tennis:migrate', 60)"))).scalar()
        if locked != 1:
            raise SystemExit("could not acquire tennis:migrate lock")
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "alembic",
                "upgrade",
                "head",
                cwd=_API_ROOT,
            )
            code = await process.wait()
            if code != 0:
                raise SystemExit(code)
        finally:
            await connection.execute(text("SELECT RELEASE_LOCK('tennis:migrate')"))
            await connection.commit()
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--if-enabled", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if args.if_enabled and not settings.run_migrations_on_start:
        print("migrations skipped")
        return
    asyncio.run(_upgrade())


if __name__ == "__main__":
    main()
