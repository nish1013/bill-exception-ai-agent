from django.core.management.base import BaseCommand

from config.celery import app
from payables.adapters.broker import CeleryPublisher, declare_queues
from payables.adapters.outbox import OutboxRelay
from payables.entrypoints.relay import RelayLoop


class Command(BaseCommand):
    help = "Publish outbox messages to the broker and re-enqueue stale check jobs."

    def handle(self, *args, **options) -> None:
        with app.connection_for_write() as connection:
            declare_queues(connection)
        RelayLoop(OutboxRelay(CeleryPublisher(app))).run()
