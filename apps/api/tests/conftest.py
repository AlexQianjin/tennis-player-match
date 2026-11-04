import os

os.environ["APP_ENV"] = "test"
os.environ["AUTH_MODE"] = "wxcloud"
os.environ["WECHAT_APPID"] = "wx-test"
os.environ["CBR_ENV_ID"] = "test-env"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["LLM_ENABLED"] = "false"
os.environ.setdefault("MYSQL_ADDRESS", "127.0.0.1:3306")
os.environ.setdefault("MYSQL_USERNAME", "tennis")
os.environ.setdefault("MYSQL_PASSWORD", "tennis")
os.environ.setdefault("MYSQL_DATABASE", "tennis")

import pytest
from httpx import ASGITransport, AsyncClient

from tennis_match_api.config import get_settings
from tennis_match_api.main import create_app


@pytest.fixture
async def client():
    get_settings.cache_clear()
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
