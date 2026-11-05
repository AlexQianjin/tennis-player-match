from pathlib import Path

_SQL = Path(__file__).resolve().parents[2] / "migrations" / "sql" / "0001_init.sql"
_TABLES = (
    "app_user",
    "court",
    "match_request",
    "application",
    "match_participant",
    "match_rating",
    "llm_match_cache",
    "llm_usage_daily",
    "state_transition_log",
)


def test_init_sql_contains_validated_tables() -> None:
    text = _SQL.read_text(encoding="utf-8")
    assert "CREATE DATABASE" not in text
    assert "USE tennis" not in text
    for table in _TABLES:
        assert f"CREATE TABLE {table} " in text
