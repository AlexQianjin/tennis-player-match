def wx_headers(openid: str, **extra: str) -> dict[str, str]:
    headers = {
        "X-WX-SOURCE": "wx_devtools",
        "X-WX-OPENID": openid,
        "X-WX-APPID": "wx-test",
        "X-WX-ENV": "test-env",
    }
    headers.update(extra)
    return headers


def complete_profile(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "nickname": "张三",
        "avatar": "cloud://test-env.bucket/avatars/a.jpg",
        "ntrp": 3.5,
        "gender": "male",
        "age": 30,
        "city": "武汉",
        "style": ["doubles", "casual"],
        "bio": "周末打双打",
    }
    body.update(overrides)
    return body
