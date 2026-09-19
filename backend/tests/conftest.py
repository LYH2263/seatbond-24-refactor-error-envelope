import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Hall, Showtime


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = TestingSession()
    hall = Hall(name="测试厅", rows=6, cols=10, aisle_cols="4,5")
    db.add(hall)
    db.flush()
    show = Showtime(hall_id=hall.id, film_title="测试片", start_at=datetime(2026, 10, 1, 10, 0, 0))
    db.add(show)
    db.commit()
    db.refresh(show)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def _get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db
    # 不用 with（不触发 lifespan，避免连真实 Postgres）；表已由夹具创建。
    # raise_server_exceptions=False：让 500 兜底处理器返回 JSON 包络而非在测试中抛出。
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def showtime_id(db_session):
    return db_session.query(Showtime).first().id
