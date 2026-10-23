"""行程工作台与装备清单的测试。

重点不是「接口返回 200」，而是几个真会出错的判断：
1. 装备清单的温度档位（-5℃ 和 32℃ 带的东西完全不同，分错档等于给错建议）；
2. 归属隔离（A 用户不能看/改/删 B 的行程）；
3. 勾选进度只算一次口径（行前清单 + 每日行程合在一起，不是分开算）；
4. 重新生成清单不能把用户手加的条目一起抹掉。
"""

import datetime

import pytest

from app import trips
from app.tools import packing

# ---------------------------------------------------------------- 装备清单


def _titles(groups):
    return [i for g in groups for i in g["items"]]


def test_freezing_band_needs_down_jacket():
    items = _titles(packing.build("哈尔滨", days=3, start_date="2026-01-10", tmax=-5, tmin=-18))
    joined = " ".join(items)
    assert "羽绒服" in joined
    assert "手套" in joined
    assert "暖宝宝" in joined


def test_hot_band_needs_sunscreen():
    items = _titles(packing.build("三亚", days=3, start_date="2026-07-10", tmax=33, tmin=27))
    joined = " ".join(items)
    assert "防晒" in joined
    assert "防蚊" in joined
    # 高温不该让人带羽绒服
    assert "羽绒服" not in joined


def test_rain_forecast_adds_umbrella():
    items = _titles(packing.build("成都", days=2, start_date="2026-05-01", tmax=22, tmin=16, precip=70))
    assert any("雨具" in i or "雨衣" in i for i in items)


def test_coastal_city_adds_swimwear():
    items = _titles(packing.build("厦门", days=3, start_date="2026-07-01", tmax=30, tmin=25))
    assert any("泳衣" in i for i in items)


def test_plateau_city_adds_sunscreen_and_oxygen():
    items = _titles(packing.build("拉萨", days=4, start_date="2026-08-01", tmax=22, tmin=10))
    joined = " ".join(items)
    assert "高原" in joined or "葡萄糖" in joined


def test_no_forecast_is_labelled_as_estimate():
    """没有预报时不能假装精确：必须明确写出这是按季节估算的。"""
    groups = packing.build("北京", days=3, start_date="2027-03-01")
    assert any(g["group"] == "说明" for g in groups)
    assert any("出发前 3 天" in i for i in _titles(groups))


def test_wash_count_is_capped():
    """30 天行程不会让你带 30 套内衣，按 5 套算 + 中途洗。"""
    items = _titles(packing.build("北京", days=30, start_date="2026-11-01", tmax=15))
    assert any("5 套" in i for i in items)


def test_items_of_keeps_group():
    groups = packing.build("北京", days=2, start_date="2026-11-01", tmax=15)
    flat = packing.items_of(groups)
    assert flat and all({"group", "title"} == set(x) for x in flat)
    assert len(flat) == len(_titles(groups))


# ---------------------------------------------------------------- 行程 CRUD


def test_create_and_progress():
    t = trips.create_trip("alice", "北京", start_date="2099-11-01", days=3, budget=3000)
    assert t["title"] == "北京 3 天"
    assert t["progress"] == {"done": 0, "total": 0, "percent": 0}
    assert t["phase"] == "upcoming" and t["countdown"] > 0

    trips.add_item(t["id"], "alice", "故宫", day_index=1, slot="上午")
    trips.add_item(t["id"], "alice", "身份证", day_index=0, slot="证件与票据")
    t2 = trips.get_trip(t["id"], username="alice")
    assert t2["progress"]["total"] == 2
    assert len(t2["prep"]) == 1 and len(t2["itinerary"]) == 1


def test_progress_counts_prep_and_itinerary_together():
    """行前清单和每日行程必须合成一个进度，否则用户看到两个互相矛盾的百分比。"""
    t = trips.create_trip("alice", "上海", days=2)
    trips.add_item(t["id"], "alice", "订酒店", day_index=0)
    a = trips.add_item(t["id"], "alice", "外滩", day_index=1)
    trips.update_item(t["id"], "alice", a["id"], done=True)
    t2 = trips.get_trip(t["id"], username="alice")
    assert t2["progress"] == {"done": 1, "total": 2, "percent": 50}


def test_ownership_isolation():
    a = trips.create_trip("alice", "北京", days=2)
    assert trips.get_trip(a["id"], username="bob") is None
    assert trips.update_trip(a["id"], "bob", title="偷改") is False
    assert trips.delete_trip(a["id"], "bob") is False
    assert trips.add_item(a["id"], "bob", "偷加") is None
    # 原主人仍能正常访问
    assert trips.get_trip(a["id"], username="alice") is not None


def test_validation_errors():
    with pytest.raises(trips.TripError):
        trips.create_trip("alice", "")
    with pytest.raises(trips.TripError):
        trips.create_trip("alice", "北京", days=0)
    with pytest.raises(trips.TripError):
        trips.create_trip("alice", "北京", days=99)
    with pytest.raises(trips.TripError):
        trips.create_trip("alice", "北京", start_date="2026/11/01")
    with pytest.raises(trips.TripError):
        trips.create_trip("alice", "北京", start_date="2026-02-30")


def test_delete_cascades_items():
    t = trips.create_trip("alice", "北京", days=2)
    trips.add_item(t["id"], "alice", "故宫", day_index=1)
    assert trips.delete_trip(t["id"], "alice") is True
    assert trips.get_trip(t["id"], username="alice") is None
    assert trips._items_of(t["id"]) == []


def test_phase_transitions():
    today = datetime.date.today()
    past = (today - datetime.timedelta(days=10)).isoformat()
    t = trips.create_trip("alice", "北京", start_date=past, days=3)
    assert t["phase"] == "past"
    ongoing = (today - datetime.timedelta(days=1)).isoformat()
    t2 = trips.create_trip("alice", "北京", start_date=ongoing, days=3)
    assert t2["phase"] == "ongoing"


# ---------------------------------------------------------------- 装备清单落库


def test_generate_packing_keeps_manual_items():
    """重新生成清单只替换 packing 类条目，用户手加的「订酒店」不能被清掉。"""
    t = trips.create_trip("alice", "北京", days=3, start_date="2026-11-01")
    trips.add_item(t["id"], "alice", "给朋友带礼物", day_index=0, kind="doc")
    trips.generate_packing(t["id"], "alice")
    first = trips.get_trip(t["id"], username="alice")
    n1 = len(first["prep"])
    assert n1 > 5
    assert any("给朋友带礼物" in i["title"] for i in first["prep"])

    # 再生成一次：数量不翻倍（旧 packing 被替换，而不是叠加）
    trips.generate_packing(t["id"], "alice")
    second = trips.get_trip(t["id"], username="alice")
    assert len(second["prep"]) == n1


def test_packing_is_grouped_by_slot():
    t = trips.create_trip("alice", "北京", days=3, start_date="2026-11-01")
    trips.generate_packing(t["id"], "alice")
    prep = trips.get_trip(t["id"], username="alice")["prep"]
    groups = {i["slot"] for i in prep}
    assert "证件与票据" in groups
    assert "行前预订" in groups


# ---------------------------------------------------------------- AI 生成


def test_parse_plan_handles_wrapped_json():
    raw = '```json\n[{"day":1,"slot":"上午","title":"故宫","kind":"spot"}]\n```'
    out = trips._parse_plan(raw)
    assert out[0]["title"] == "故宫"


def test_parse_plan_rejects_garbage():
    with pytest.raises(trips.TripError):
        trips._parse_plan("今天天气不错")


def test_plan_trip_without_llm_is_readable_error():
    """mock 模式没有模型：要给人话，而不是 500 或静默失败。"""
    t = trips.create_trip("alice", "北京", days=2)
    with pytest.raises(trips.TripError) as e:
        trips.plan_trip(t["id"], "alice")
    assert "手动添加" in str(e.value)


# ---------------------------------------------------------------- 接口层


def test_api_requires_login(client):
    assert client.get("/api/trips").status_code == 401


def test_api_crud_roundtrip(client, admin_headers):
    r = client.post("/api/trips", json={"city": "杭州", "days": 2, "budget": 1500}, headers=admin_headers)
    assert r.status_code == 200, r.text
    tid = r.json()["trip"]["id"]

    r = client.post(
        f"/api/trips/{tid}/items",
        json={"title": "西湖", "day_index": 1, "slot": "上午"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    iid = r.json()["item"]["id"]

    r = client.patch(f"/api/trips/{tid}/items/{iid}", json={"done": True}, headers=admin_headers)
    assert r.json()["trip"]["progress"]["done"] == 1

    r = client.post(f"/api/trips/{tid}/packing", headers=admin_headers)
    assert r.status_code == 200 and r.json()["groups"]

    r = client.get(f"/api/trips/{tid}", headers=admin_headers)
    assert r.json()["trip"]["itinerary"][0]["day"] == 1

    assert client.delete(f"/api/trips/{tid}", headers=admin_headers).status_code == 200
    assert client.get(f"/api/trips/{tid}", headers=admin_headers).status_code == 404


def test_api_rejects_bad_days(client, admin_headers):
    r = client.post("/api/trips", json={"city": "北京", "days": 0}, headers=admin_headers)
    assert r.status_code == 400
    assert "天数" in r.json()["detail"]


def test_api_other_users_trip_is_404(client, admin_headers):
    r = client.post("/api/trips", json={"city": "北京", "days": 2}, headers=admin_headers)
    tid = r.json()["trip"]["id"]
    # 用另一个账号访问
    client.post("/api/auth/register", json={"username": "bobtrip", "password": "bob12345"})
    tok = client.post("/api/auth/login", json={"username": "bobtrip", "password": "bob12345"}).json()["token"]
    assert client.get(f"/api/trips/{tid}", headers={"X-Auth-Token": tok}).status_code == 404
