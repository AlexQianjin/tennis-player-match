from uuid import uuid4


def _headers(openid: str) -> dict[str, str]:
    return {
        "X-WX-SOURCE": "wx_devtools",
        "X-WX-OPENID": openid,
        "X-WX-APPID": "wx-test",
        "X-WX-ENV": "test-env",
    }


async def test_login_creates_user_and_courts_list(client) -> None:
    response = await client.post("/api/v1/auth/login", headers=_headers(f"it-{uuid4().hex}"))
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["isNewUser"] is True
    assert body["data"]["userInfo"]["profileCompleted"] is False
    assert body["data"]["userInfo"]["id"]

    courts = await client.get("/api/v1/courts", params={"city": "武汉"})
    assert courts.status_code == 200
    assert isinstance(courts.json()["data"]["list"], list)
