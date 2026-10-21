from collections.abc import Callable

import redis
from django.conf import settings
from django.db import connection
from kombu import Connection

TIMEOUT_SECONDS = 2

Probe = Callable[[], None]


def probe_postgres() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def probe_redis() -> None:
    client = redis.Redis.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=TIMEOUT_SECONDS,
        socket_timeout=TIMEOUT_SECONDS,
    )
    try:
        client.ping()
    finally:
        client.close()


def probe_rabbitmq() -> None:
    with Connection(settings.CELERY_BROKER_URL, connect_timeout=TIMEOUT_SECONDS) as broker:
        broker.ensure_connection(max_retries=1)


PROBES: dict[str, Probe] = {
    "postgres": probe_postgres,
    "redis": probe_redis,
    "rabbitmq": probe_rabbitmq,
}
