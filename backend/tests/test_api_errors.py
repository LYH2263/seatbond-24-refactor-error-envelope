"""错误响应包络契约测试。

所有失败响应均须满足：
    HTTP 4xx + application/json
    body = {"error": {"code": ..., "message": ..., "details": {...}}}

code 约定：
- 404 资源不存在        -> "not_found"          （details.resource 指明资源）
- 409 空座不足          -> "seats_unavailable"  （details.reason 同名）
- 409 与既有持座重叠    -> "seat_overlap"       （details.reason 同名，带 conflicting_holds）
- 422 参数不合法        -> "validation_error"
"""

from app.models.models import ConflictLog, SeatHold
from app.services.bond_engine import HoldSpan


def _assert_envelope(payload: dict, expected_code: str):
    """包络形状与稳定键断言：error.code / error.message / error.details 齐备。"""
    assert set(payload.keys()) == {"error"}
    err = payload["error"]
    assert set(err.keys()) >= {"code", "message", "details"}
    assert err["code"] == expected_code
    assert isinstance(err["message"], str) and err["message"]
    assert isinstance(err["details"], dict)


# ---------- 404 资源不存在 ----------

def test_create_hold_unknown_showtime_404(client):
    resp = client.post("/api/holds", json={"showtime_id": 999999, "party_size": 2})
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    data = resp.json()
    _assert_envelope(data, "not_found")
    assert data["error"]["details"]["resource"] == "showtime"
    assert data["error"]["details"]["showtime_id"] == 999999


def test_seatmap_unknown_showtime_404(client):
    resp = client.get("/api/seatmap/888888")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    data = resp.json()
    _assert_envelope(data, "not_found")
    assert data["error"]["details"]["resource"] == "showtime"
    assert data["error"]["details"]["showtime_id"] == 888888


def test_unknown_route_is_json_envelope_not_html(client):
    resp = client.get("/no-such-path")
    assert resp.status_code == 404
    # 框架默认 404 是 HTML 或 {"detail": ...}；现须统一为 JSON 包络
    assert resp.headers["content-type"].startswith("application/json")
    _assert_envelope(resp.json(), "not_found")


# ---------- 409 空座不足 ----------

def test_hold_insufficient_seats_409(client, showtime_id, db_session):
    # 测试厅 6×10、过道 4,5 列：每排最长连续段为 5 座；8 人无处可放
    resp = client.post("/api/holds", json={"showtime_id": showtime_id, "party_size": 8})
    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("application/json")
    data = resp.json()
    _assert_envelope(data, "seats_unavailable")
    details = data["error"]["details"]
    assert details["reason"] == "seats_unavailable"
    assert details["showtime_id"] == showtime_id
    assert details["party_size"] == 8
    # 业务规则保留：失败也要落冲突日志，且不产生持座
    logs = db_session.query(ConflictLog).filter_by(showtime_id=showtime_id).all()
    assert len(logs) == 1 and "空座" in logs[0].reason
    assert db_session.query(SeatHold).count() == 0


# ---------- 409 与既有持座重叠（并发竞态守卫分支） ----------

def test_hold_overlap_409(client, showtime_id, db_session, monkeypatch):
    import app.api.router as router_mod

    # 正常选座会避开既有持座，重叠只可能在读座之后、提交之前被他人抢先（竞态）。
    # 这里强制冲突检测命中，验证守卫分支的包络与 details 契约。
    forced = [HoldSpan(row=1, start_col=1, end_col=3)]
    monkeypatch.setattr(router_mod, "conflicts_with", lambda existing, candidate: forced)

    resp = client.post("/api/holds", json={"showtime_id": showtime_id, "party_size": 3})
    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("application/json")
    data = resp.json()
    _assert_envelope(data, "seat_overlap")
    details = data["error"]["details"]
    assert details["reason"] == "seat_overlap"
    assert details["party_size"] == 3
    assert details["conflicting_holds"] == [
        {"row": 1, "start_col": 1, "end_col": 3}
    ]
    logs = db_session.query(ConflictLog).filter_by(showtime_id=showtime_id).all()
    assert len(logs) == 1 and "重叠" in logs[0].reason
    assert db_session.query(SeatHold).count() == 0


# ---------- 422 参数校验同样走包络 ----------

def test_validation_error_422_envelope(client, showtime_id):
    resp = client.post("/api/holds", json={"showtime_id": showtime_id, "party_size": 99})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")
    _assert_envelope(resp.json(), "validation_error")


# ---------- 成功路径：主字段名保持不变 ----------

def test_create_hold_success_shape_unchanged(client, showtime_id):
    resp = client.post("/api/holds", json={"showtime_id": showtime_id, "party_size": 3})
    assert resp.status_code == 200
    data = resp.json()
    # 包络仅用于错误；成功响应主字段名与现网一致
    assert set(data.keys()) == {
        "id",
        "showtime_id",
        "order_code",
        "row",
        "start_col",
        "end_col",
        "party_size",
        "status",
    }
    assert data["showtime_id"] == showtime_id
    assert data["party_size"] == 3
    assert data["status"] == "held"
    assert isinstance(data["order_code"], str) and data["order_code"]


def test_conflict_codes_are_distinct(client, showtime_id, monkeypatch):
    """空座不足与重叠必须可用 code 稳定区分。"""
    import app.api.router as router_mod

    r1 = client.post("/api/holds", json={"showtime_id": showtime_id, "party_size": 8})
    assert r1.json()["error"]["code"] == "seats_unavailable"

    monkeypatch.setattr(
        router_mod,
        "conflicts_with",
        lambda existing, candidate: [HoldSpan(row=2, start_col=6, end_col=8)],
    )
    r2 = client.post("/api/holds", json={"showtime_id": showtime_id, "party_size": 3})
    assert r2.json()["error"]["code"] == "seat_overlap"
    assert r1.json()["error"]["code"] != r2.json()["error"]["code"]
