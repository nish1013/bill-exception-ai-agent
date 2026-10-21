import logging
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Django loads the apps before the consumer imports models.
django_application = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from payables.entrypoints.ws.redact_token_filter import RedactTokenFilter  # noqa: E402
from payables.entrypoints.ws.routes import websocket_urlpatterns  # noqa: E402

for name in ("uvicorn.error", "uvicorn.access"):
    logging.getLogger(name).addFilter(RedactTokenFilter())

application = ProtocolTypeRouter(
    {"http": django_application, "websocket": URLRouter(websocket_urlpatterns)}
)
