"""Dev-only fixtures. The M0 stub refuses production and does not invent users."""

from tennis_match_api.config import Settings


def load_dev_fixtures(settings: Settings) -> None:
    if settings.app_env == "prod":
        raise SystemExit("dev fixtures are forbidden when APP_ENV=prod")
    print("dev fixtures are not implemented in this milestone")
