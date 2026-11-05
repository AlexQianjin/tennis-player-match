"""Apply the validated MySQL 8.0 schema.

Revision ID: 0001_init
Revises:
Create Date: 2026-11-04
"""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None

_SQL_PATH = Path(__file__).resolve().parents[1] / "sql" / "0001_init.sql"
_DROP_ORDER = (
    "state_transition_log",
    "llm_usage_daily",
    "llm_match_cache",
    "match_rating",
    "match_participant",
    "application",
    "match_request",
    "court",
    "app_user",
)


def _statements(script: str) -> list[str]:
    buffer: list[str] = []
    statements: list[str] = []
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buffer.append(line)
        if stripped.endswith(";"):
            statement = "\n".join(buffer).strip().rstrip(";").strip()
            if statement:
                statements.append(statement)
            buffer = []
    if buffer:
        raise RuntimeError("0001_init.sql has an unterminated statement")
    return statements


def upgrade() -> None:
    for statement in _statements(_SQL_PATH.read_text(encoding="utf-8")):
        op.execute(sa.text(statement))


def downgrade() -> None:
    for table in _DROP_ORDER:
        op.execute(sa.text(f"DROP TABLE IF EXISTS {table}"))
