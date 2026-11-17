import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from alembic.config import Config
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import create_async_engine

from tennis_match_api.config import get_settings
from tennis_match_api.db import connect_migrator

# Image WORKDIR. The console script is installed into site-packages, so this
# file's parents are not the directory that holds alembic.ini.
_IMAGE_ROOT = Path("/app")


def _script_dir(directory: Path) -> Path | None:
    ini = directory / "alembic.ini"
    if not ini.is_file() or not (directory / "migrations" / "env.py").is_file():
        return None
    location = Config(str(ini)).get_alembic_option("script_location")
    if not location:
        return None
    script_path = Path(location)
    if not script_path.is_absolute():
        script_path = directory / script_path
    if not (script_path / "env.py").is_file():
        return None
    return script_path


def resolve_api_root(
    module_file: Path | None = None,
    cwd: Path | None = None,
    fallback_roots: Sequence[Path] | None = None,
) -> Path:
    """Locate alembic.ini independent of the process cwd and install layout.

    ``uv run`` uses this source file, whose parents include ``apps/api``.
    The image runs ``uv pip install --no-deps .``, so ``__file__`` is under
    site-packages and ``parents[3]`` is ``.../python3.12``. Alembic then starts
    with no config file and exits with
    ``No 'script_location' key found in configuration.``
    """
    module_file = (module_file or Path(__file__)).resolve()
    cwd = (cwd or Path.cwd()).resolve()
    if fallback_roots is None:
        fallback_roots = (_IMAGE_ROOT,)

    env_root = os.environ.get("TENNIS_API_ROOT")
    if env_root:
        root = Path(env_root).expanduser().resolve()
        if _script_dir(root) is not None:
            return root
        raise SystemExit(
            f"TENNIS_API_ROOT={root} has no alembic.ini script_location and migrations/env.py"
        )

    candidates: list[Path] = [
        *module_file.parents,
        *fallback_roots,
        cwd,
        *cwd.parents,
    ]
    searched: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        searched.append(resolved)
        if _script_dir(resolved) is not None:
            return resolved

    listed = ", ".join(str(path) for path in searched)
    raise SystemExit(
        "Could not find alembic.ini with script_location and migrations/env.py. "
        f"Looked at: {listed}"
    )


def alembic_argv(root: Path, *args: str) -> list[str]:
    return [sys.executable, "-m", "alembic", "-c", str(root / "alembic.ini"), *args]


def migration_command(
    module_file: Path | None = None,
    cwd: Path | None = None,
    fallback_roots: Sequence[Path] | None = None,
) -> tuple[list[str], Path]:
    root = resolve_api_root(module_file=module_file, cwd=cwd, fallback_roots=fallback_roots)
    return alembic_argv(root, "upgrade", "head"), root


async def _upgrade() -> None:
    argv, root = migration_command()
    print(f"alembic config: {root / 'alembic.ini'}", flush=True)
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
            process = await asyncio.create_subprocess_exec(*argv, cwd=root)
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
