from uuid import uuid4

from tennis_match_api.db import get_sessionmaker
from tennis_match_api.models import Court


async def test_courts_filter_by_city_and_skip_inactive(client) -> None:
    city = f"c{uuid4().hex[:12]}"
    other = f"c{uuid4().hex[:12]}"
    active_late = f"late-{uuid4().hex}"
    active_early = f"early-{uuid4().hex}"
    inactive = f"inactive-{uuid4().hex}"
    removed = f"removed-{uuid4().hex}"
    elsewhere = f"elsewhere-{uuid4().hex}"
    factory = get_sessionmaker()
    async with factory() as session:
        session.add_all(
            [
                Court(
                    name=active_late,
                    city=city,
                    district="甲区",
                    address="地址甲",
                    sort_order=20,
                    is_active=True,
                ),
                Court(
                    name=active_early,
                    city=city,
                    district="乙区",
                    address="地址乙",
                    sort_order=10,
                    is_active=True,
                ),
                Court(
                    name=inactive,
                    city=city,
                    district="甲区",
                    address="地址丙",
                    sort_order=5,
                    is_active=False,
                ),
                Court(
                    name=removed,
                    city=city,
                    district="甲区",
                    address="地址丁",
                    sort_order=1,
                    is_active=True,
                    is_deleted=True,
                ),
                Court(
                    name=elsewhere,
                    city=other,
                    district="甲区",
                    address="地址戊",
                    sort_order=1,
                    is_active=True,
                ),
            ]
        )
        await session.commit()

    response = await client.get("/api/v1/courts", params={"city": city})
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    names = [item["name"] for item in body["data"]["list"]]
    assert names == [active_early, active_late]
    assert body["data"]["list"][0]["district"] == "乙区"
    assert body["data"]["list"][0]["address"] == "地址乙"

    empty = await client.get("/api/v1/courts", params={"city": f"missing-{uuid4().hex}"})
    assert empty.status_code == 200
    assert empty.json()["data"]["list"] == []
