async def test_login_without_wechat_headers_is_401(client) -> None:
    response = await client.post("/api/v1/auth/login")
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == 401
    assert body["data"] is None


async def test_dev_openid_is_ignored_in_wxcloud_mode(client) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        headers={"X-Dev-Openid": "dev_user_1"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_login_rejects_mismatched_appid(client) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        headers={
            "X-WX-SOURCE": "wx_devtools",
            "X-WX-OPENID": "openid-1",
            "X-WX-APPID": "wrong",
            "X-WX-ENV": "test-env",
        },
    )
    assert response.status_code == 401
    assert response.json()["code"] == 401
