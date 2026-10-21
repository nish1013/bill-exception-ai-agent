import os

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = ["payables"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"


def _database(user_variable: str, password_variable: str) -> dict:
    return {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.environ["POSTGRES_HOST"],
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "NAME": os.environ["POSTGRES_DB"],
        "USER": os.environ[user_variable],
        "PASSWORD": os.environ[password_variable],
        "OPTIONS": {"connect_timeout": 2},
    }


# default is the app role, which row-level security filters. owner owns the tables and migrates.
# relay bypasses row-level security on the outbox and check_job tables only (D7).
DATABASES = {
    "default": _database("POSTGRES_APP_USER", "POSTGRES_APP_PASSWORD"),
    "owner": _database("POSTGRES_USER", "POSTGRES_PASSWORD"),
    "relay": _database("POSTGRES_RELAY_USER", "POSTGRES_RELAY_PASSWORD"),
}

MIGRATION_MODULES = {"payables": "payables.adapters.orm.migrations"}

REDIS_URL = os.environ["REDIS_URL"]

# Console events go through Redis to the socket consumers (D47). The prefix keeps test runs apart.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
            "prefix": os.environ.get("CHANNEL_LAYER_PREFIX", "asgi"),
            "expiry": 60,
            "capacity": 100,
        },
    }
}

CELERY_BROKER_URL = os.environ["CELERY_BROKER_URL"]
# At least once (D43): ack after the task, requeue when the worker dies, confirm each publish.
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_ACKS_ON_FAILURE_OR_TIMEOUT = False
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_TRANSPORT_OPTIONS = {"confirm_publish": True}
CELERY_TASK_IGNORE_RESULT = True
CELERY_IMPORTS = ["payables.entrypoints.tasks"]

# The stub model runs in CI and the demo. It makes no network call and needs no key (D54).
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "stub")
RATE_LIMIT_PREFIX = os.environ.get("RATE_LIMIT_PREFIX", "ratelimit")

CHECK_LOCK_TIMEOUT_MS = int(os.environ.get("CHECK_LOCK_TIMEOUT_MS", "5000"))

OIDC_ISSUER = os.environ["OIDC_ISSUER"]
OIDC_JWKS_URL = os.environ["OIDC_JWKS_URL"]
OIDC_AUDIENCE = os.environ["OIDC_AUDIENCE"]

USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
