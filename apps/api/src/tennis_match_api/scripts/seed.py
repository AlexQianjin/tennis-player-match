"""Import courts from CSV.

``seed/courts_wuhan.csv`` is still placeholder data: every name, district, and
address contains ``TODO``. Real Wuhan venues are a product-owner task and must
not be invented in this repo. Replace that CSV later; rows are upserted by
``(city, name)`` and the court API does not need to change.

``--allow-placeholder`` is for local/CI only. ``APP_ENV=prod`` refuses the file
while any placeholder row remains.
"""

import argparse
import asyncio
import csv
import importlib.util
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from tennis_match_api.config import get_settings
from tennis_match_api.db import dispose_engine, get_sessionmaker
from tennis_match_api.models import Court

_API_ROOT = Path(__file__).resolve().parents[3]


def _is_placeholder(row: dict[str, str]) -> bool:
    return any("TODO" in (row.get(column) or "") for column in ("name", "district", "address"))


def validate_court_rows(
    rows: list[dict[str, str]],
    *,
    app_env: str,
    allow_placeholder: bool,
) -> None:
    placeholders = [row for row in rows if _is_placeholder(row)]
    if app_env == "prod" and placeholders:
        raise SystemExit("refusing placeholder courts when APP_ENV=prod")
    if placeholders and not allow_placeholder:
        raise SystemExit("placeholder court rows require --allow-placeholder")


def _decimal(value: str) -> Decimal | None:
    text = value.strip()
    if not text:
        return None
    return Decimal(text)


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


def _load_dev_fixtures() -> None:
    path = _API_ROOT / "seed" / "dev_fixtures.py"
    spec = importlib.util.spec_from_file_location("tennis_dev_fixtures", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.load_dev_fixtures(get_settings())


async def _import_courts(path: Path, *, allow_placeholder: bool) -> None:
    settings = get_settings()
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    validate_court_rows(rows, app_env=settings.app_env, allow_placeholder=allow_placeholder)

    factory = get_sessionmaker()
    async with factory() as session:
        for row in rows:
            name = row["name"].strip()
            city = row["city"].strip()
            existing = await session.scalar(
                select(Court).where(
                    Court.city == city,
                    Court.name == name,
                    Court.is_deleted.is_(False),
                )
            )
            payload = {
                "district": (row.get("district") or "").strip() or None,
                "address": row["address"].strip(),
                "latitude": _decimal(row.get("latitude") or ""),
                "longitude": _decimal(row.get("longitude") or ""),
                "sort_order": int(row.get("sort_order") or 0),
                "is_active": _bool(row.get("is_active") or "true"),
            }
            if existing is None:
                session.add(Court(name=name, city=city, **payload))
            else:
                for key, value in payload.items():
                    setattr(existing, key, value)
        await session.commit()
    await dispose_engine()
    print(f"imported {len(rows)} court rows from {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--courts", type=Path)
    parser.add_argument("--allow-placeholder", action="store_true")
    parser.add_argument("--dev-fixtures", action="store_true")
    args = parser.parse_args()
    if not args.dev_fixtures and args.courts is None:
        parser.error("pass --courts and/or --dev-fixtures")
    if args.dev_fixtures:
        _load_dev_fixtures()
    if args.courts is not None:
        asyncio.run(_import_courts(args.courts, allow_placeholder=args.allow_placeholder))


if __name__ == "__main__":
    main()
