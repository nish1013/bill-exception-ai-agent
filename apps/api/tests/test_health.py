import pytest

from payables.adapters import readiness

UNREACHABLE_BROKER = "amqp://guest:guest@unreachable.invalid:5672//"
UNREACHABLE_REDIS = "redis://unreachable.invalid:6379/0"


def test_healthz_ok_with_no_db_access(client):
    response = client.get("/healthz")

    assert response.status_code == 200


@pytest.mark.django_db
def test_readyz_ok_when_all_answer(client):
    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"postgres": "ok", "redis": "ok", "rabbitmq": "ok"}


@pytest.mark.django_db
def test_readyz_503_when_broker_down(client, settings):
    settings.CELERY_BROKER_URL = UNREACHABLE_BROKER

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"postgres": "ok", "redis": "ok", "rabbitmq": "error"}


@pytest.mark.django_db
def test_readyz_503_when_redis_down(client, settings):
    settings.REDIS_URL = UNREACHABLE_REDIS

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"postgres": "ok", "redis": "error", "rabbitmq": "ok"}


def test_readyz_503_when_postgres_down(client, monkeypatch):
    def refuse() -> None:
        raise OSError("connection refused")

    monkeypatch.setitem(readiness.PROBES, "postgres", refuse)

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["postgres"] == "error"
