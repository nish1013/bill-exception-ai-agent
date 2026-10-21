import os

from celery import Celery
from celery.signals import worker_init

from payables.adapters.broker.queues import ALL_QUEUES, declare_queues

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("payables")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.task_queues = ALL_QUEUES


@worker_init.connect
def _declare_queues(**_kwargs) -> None:
    with app.connection_for_write() as connection:
        declare_queues(connection)
