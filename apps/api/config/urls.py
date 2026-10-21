from django.urls import path

from payables.entrypoints.rest.health import healthz, readyz

urlpatterns = [
    path("healthz", healthz),
    path("readyz", readyz),
]
