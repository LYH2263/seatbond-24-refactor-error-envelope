"""API contract tests: all error responses share the {code, message, details?} envelope."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.errors import ErrorCode
from app.main import app
from app.models.models import Hall, SeatHold, Showtime
from app.services.bond_engine import HoldSpan


@pytest.fixture()
def client():
    # Hall: 1 row x 6 cols, aisle at col 3 -> runs (1,2) and (4,6).
    # Existing hold occupies row 1 cols 1-2, so only cols 4-6 are free.
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        hall = Hall(name="测试厅", rows=1, cols=6, aisle_cols="3")
        db.add(hall)
        db.flush()
        st = Showtime(hall_id=hall.id, film_title="测试片", start_at=datetime(2030, 1, 1, 20, 0))
        db.add(st)
        db.flush()
        db.add(
            SeatHold(showtime_id=st.id, order_code="SB-T001", row=1, start_col=1, end_col=2, party_size=2)
        )
        db.commit()
        showtime_id = st.id
    finally:
        db.close()
    with TestClient(app) as c:
        yield c, showtime_id


def _assert_envelope(res, status: int, code: str):
    assert res.status_code == status
    assert res.headers["content-type"].startswith("application/json")
    body = res.json()
    assert body["code"] == code
    assert isinstance(body["message"], str) and body["message"]
    return body


def test_hold_showtime_not_found_envelope(client):
    c, _ = client
    res = c.post("/api/holds", json={"showtime_id": 9999, "party_size": 2})
    body = _assert_envelope(res, 404, ErrorCode.SHOWTIME_NOT_FOUND)
    assert body["details"]["showtime_id"] == 9999


def test_seatmap_showtime_not_found_envelope(client):
    c, _ = client
    res = c.get("/api/seatmap/9999")
    body = _assert_envelope(res, 404, ErrorCode.SHOWTIME_NOT_FOUND)
    assert body["details"]["showtime_id"] == 9999


def test_hold_insufficient_seats_envelope(client):
    c, sid = client
    res = c.post("/api/holds", json={"showtime_id": sid, "party_size": 4})
    body = _assert_envelope(res, 409, ErrorCode.INSUFFICIENT_CONTIGUOUS_SEATS)
    assert body["details"]["reason"] == "insufficient_contiguous_seats"
    assert body["details"]["party_size"] == 4
    assert body["details"]["showtime_id"] == sid


def test_hold_overlap_envelope(client, monkeypatch):
    c, sid = client
    # Force the across-rows finder to propose a span overlapping the existing
    # hold (row 1, cols 1-2) so the defensive overlap branch is exercised.
    monkeypatch.setattr(
        "app.api.router.find_bond_across_rows",
        lambda seats, holds, party_size: HoldSpan(row=1, start_col=2, end_col=3),
    )
    res = c.post("/api/holds", json={"showtime_id": sid, "party_size": 2})
    body = _assert_envelope(res, 409, ErrorCode.HOLD_OVERLAP)
    assert body["details"]["reason"] == "overlap"
    assert (body["details"]["row"], body["details"]["start_col"], body["details"]["end_col"]) == (1, 1, 2)


def test_hold_success_shape_unchanged(client):
    c, sid = client
    res = c.post("/api/holds", json={"showtime_id": sid, "party_size": 3})
    assert res.status_code == 200
    body = res.json()
    for key in ("id", "showtime_id", "order_code", "row", "start_col", "end_col", "party_size", "status"):
        assert key in body
    assert (body["row"], body["start_col"], body["end_col"]) == (1, 4, 6)
    assert body["party_size"] == 3


def test_validation_error_envelope(client):
    c, sid = client
    res = c.post("/api/holds", json={"showtime_id": sid, "party_size": 0})
    _assert_envelope(res, 422, ErrorCode.VALIDATION_ERROR)


def test_unknown_route_envelope(client):
    c, _ = client
    res = c.get("/api/does-not-exist")
    _assert_envelope(res, 404, ErrorCode.HTTP_ERROR)
