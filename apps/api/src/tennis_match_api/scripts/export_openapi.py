import json
import os
import sys
from pathlib import Path


def _ensure_export_env() -> None:
    os.environ.setdefault("APP_ENV", "dev")
    os.environ.setdefault("AUTH_MODE", "dev")
    os.environ.setdefault("MYSQL_ADDRESS", "127.0.0.1:3306")
    os.environ.setdefault("MYSQL_USERNAME", "tennis")
    os.environ.setdefault("MYSQL_PASSWORD", "tennis")
    os.environ.setdefault("MYSQL_DATABASE", "tennis")
    os.environ.setdefault("WECHAT_APPID", "wx-test")
    os.environ.setdefault("SCHEDULER_ENABLED", "false")
    os.environ.setdefault("LLM_ENABLED", "false")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: export_openapi <path-to-openapi.json>")
    _ensure_export_env()
    from tennis_match_api.config import get_settings

    get_settings.cache_clear()
    from tennis_match_api.main import create_app

    document = create_app().openapi()
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
