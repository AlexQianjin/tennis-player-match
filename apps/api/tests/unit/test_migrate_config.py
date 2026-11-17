"""Startup migration config must load outside a source checkout.

The cloud image installs this package into site-packages and starts with cwd
`/`. Alembic then looks for `alembic.ini` in the wrong directory and exits
with `No 'script_location' key found in configuration.` before uvicorn binds.
`heads` below only reads revision files. It does not connect and does not
apply DDL. The optional upgrade test runs only when TEST_DATABASE_URL points
at a reachable test database, and it fails if that upgrade fails.
"""

import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from tennis_match_api.config import get_settings
from tennis_match_api.scripts.migrate import alembic_argv, migration_command, resolve_api_root

_API_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_MODULE = _API_ROOT / "src" / "tennis_match_api" / "scripts" / "migrate.py"


def _installed_module(site: Path) -> Path:
    return site / "tennis_match_api" / "scripts" / "migrate.py"


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)


def test_alembic_without_config_file_matches_cloud_log(tmp_path: Path) -> None:
    result = _run([sys.executable, "-m", "alembic", "upgrade", "head"], tmp_path)
    assert result.returncode != 0
    assert "No 'script_location' key found in configuration." in result.stdout + result.stderr
    assert "0001_init" not in result.stdout


def test_source_tree_resolves_from_arbitrary_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TENNIS_API_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    argv, root = migration_command()
    assert root == _API_ROOT
    assert argv[-2:] == ["upgrade", "head"]
    assert argv[argv.index("-c") + 1] == str(_API_ROOT / "alembic.ini")
    heads = _run(alembic_argv(root, "heads"), tmp_path)
    assert heads.returncode == 0, heads.stdout + heads.stderr
    assert "0001_init" in heads.stdout


def test_installed_layout_prefers_image_root_over_parents_three(tmp_path: Path) -> None:
    image_root = tmp_path / "app"
    image_root.mkdir()
    (image_root / "alembic.ini").symlink_to(_API_ROOT / "alembic.ini")
    (image_root / "migrations").symlink_to(_API_ROOT / "migrations")
    site = tmp_path / "usr" / "local" / "lib" / "python3.12" / "site-packages"
    module = _installed_module(site)
    module.parent.mkdir(parents=True)
    module.write_text("# installed copy\n", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    wrong = module.resolve().parents[3]
    assert not (wrong / "alembic.ini").is_file()

    argv, root = migration_command(
        module_file=module,
        cwd=elsewhere,
        fallback_roots=(image_root,),
    )
    assert root == image_root.resolve()
    assert root != wrong
    assert argv[-2:] == ["upgrade", "head"]
    heads = _run([*argv[:-2], "heads"], elsewhere)
    assert heads.returncode == 0, heads.stdout + heads.stderr
    assert "0001_init" in heads.stdout
    assert "No 'script_location' key found in configuration." not in heads.stdout


def test_explicit_root_is_not_replaced_by_a_nearby_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TENNIS_API_ROOT", str(tmp_path))
    with pytest.raises(SystemExit, match="TENNIS_API_ROOT"):
        resolve_api_root(module_file=_SOURCE_MODULE, cwd=_API_ROOT)


def test_ini_without_script_location_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TENNIS_API_ROOT", raising=False)
    bad = tmp_path / "bad"
    (bad / "migrations").mkdir(parents=True)
    (bad / "migrations" / "env.py").write_text("x = 1\n", encoding="utf-8")
    (bad / "alembic.ini").write_text("[alembic]\n", encoding="utf-8")
    module = _installed_module(tmp_path / "site")
    module.parent.mkdir(parents=True)
    module.write_text("# installed\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="script_location"):
        resolve_api_root(module_file=module, cwd=bad, fallback_roots=())


def test_non_editable_install_resolves_from_arbitrary_cwd(tmp_path: Path) -> None:
    site = tmp_path / "site"
    install = subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            sys.executable,
            "--no-deps",
            "--target",
            str(site),
            str(_API_ROOT),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    installed = _installed_module(site)
    assert installed.is_file()
    assert not (installed.resolve().parents[3] / "alembic.ini").is_file()

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(site)
    env["TENNIS_API_ROOT"] = str(_API_ROOT)
    env.pop("UV_PROJECT_ENVIRONMENT", None)
    script = """
from pathlib import Path
import tennis_match_api.scripts.migrate as migrate
from tennis_match_api.scripts.migrate import migration_command
module = Path(migrate.__file__).resolve()
argv, root = migration_command()
print(module)
print(root)
print(module.parents[3])
print("\\0".join(argv))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=elsewhere,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    module_line, root_line, parents_line, argv_line = result.stdout.splitlines()
    assert module_line.startswith(str(site.resolve()))
    assert Path(root_line) == _API_ROOT
    assert Path(parents_line) != _API_ROOT
    argv = argv_line.split("\0")
    assert argv[-2:] == ["upgrade", "head"]
    assert argv[argv.index("-c") + 1] == str(_API_ROOT / "alembic.ini")
    heads = _run([*argv[:-2], "heads"], elsewhere)
    assert heads.returncode == 0, heads.stdout + heads.stderr
    assert "0001_init" in heads.stdout


def test_upgrade_head_against_test_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("TEST_DATABASE_URL is unset; not migrating an unspecified database")
    monkeypatch.delenv("TENNIS_API_ROOT", raising=False)
    host, port, *_rest = get_settings().mysql_endpoint(migration=True)
    try:
        with socket.create_connection((host, port), timeout=1):
            pass
    except OSError:
        pytest.skip(f"test database at {host}:{port} is not accepting connections")

    argv, root = migration_command(cwd=tmp_path)
    upgraded = _run(argv, tmp_path)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    current = _run(alembic_argv(root, "current"), tmp_path)
    assert current.returncode == 0, current.stdout + current.stderr
    assert "0001_init" in current.stdout


def test_users_sql_keeps_table_grants_after_migrator_grant() -> None:
    text = (_API_ROOT / "sql" / "users.sql").read_text(encoding="utf-8")
    stage_a = text.index("----- 阶段 A")
    migrator = text.index("TO 'tennis_migrator'@'%'")
    stage_b = text.index("----- 阶段 B")
    app_user = text.index("ON tennis.app_user")
    assert stage_a < migrator < stage_b < app_user
    app_section = text.split("----- 阶段 B", 1)[1]
    assert "ON tennis.*" not in app_section
    assert "ALL PRIVILEGES" not in app_section.upper()
    assert "GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX, REFERENCES" in text
