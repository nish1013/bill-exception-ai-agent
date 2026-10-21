from django.core.management.base import BaseCommand

from payables.entrypoints.graphql.schema import schema


class Command(BaseCommand):
    help = "Print the GraphQL schema as SDL. The console generates its types from it."

    def handle(self, *args, **options) -> None:
        self.stdout.write(str(schema), ending="\n")
