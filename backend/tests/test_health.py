from sqlalchemy.exc import OperationalError

from app.core.database import get_db
from app.main import app


def test_health_ok(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_reports_database_outage():
    def override():
        class Broken:
            def execute(self, *_args, **_kwargs):
                raise OperationalError("SELECT 1", {}, Exception("down"))

        yield Broken()

    app.dependency_overrides[get_db] = override
    try:
        from fastapi.testclient import TestClient

        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/health")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
