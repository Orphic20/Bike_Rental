import os

from sqlalchemy.exc import OperationalError

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://test:test@localhost:5432/test",
)

from bike_rental.routers.staff import _http_for_db_wait


def test_lock_timeout_maps_to_retryable_conflict():
    exc = OperationalError(
        "SELECT 1",
        {},
        Exception("canceling statement due to lock timeout"),
    )
    http = _http_for_db_wait(exc)
    assert http.status_code == 409
    assert "busy" in str(http.detail).lower()


def test_other_db_errors_map_to_unavailable():
    exc = OperationalError("SELECT 1", {}, Exception("server closed the connection"))
    http = _http_for_db_wait(exc)
    assert http.status_code == 503
