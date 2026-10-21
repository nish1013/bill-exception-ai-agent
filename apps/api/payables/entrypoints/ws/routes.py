from django.urls import path

from payables.entrypoints.ws.events_consumer import EventsConsumer

websocket_urlpatterns = [path("ws/events/", EventsConsumer.as_asgi())]
