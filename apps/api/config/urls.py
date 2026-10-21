from django.urls import path

from payables.entrypoints.graphql.schema import schema
from payables.entrypoints.graphql.view import TenantGraphQLView
from payables.entrypoints.rest.health import healthz, readyz

urlpatterns = [
    path("healthz", healthz),
    path("readyz", readyz),
    path("graphql", TenantGraphQLView.as_view(schema=schema)),
]
