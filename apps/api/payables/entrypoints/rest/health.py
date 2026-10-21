import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from payables.adapters.readiness import PROBES, Probe

logger = logging.getLogger(__name__)


@require_GET
def healthz(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


@require_GET
def readyz(request: HttpRequest) -> JsonResponse:
    results = {name: _run(name, probe) for name, probe in PROBES.items()}
    ready = all(result == "ok" for result in results.values())
    return JsonResponse(results, status=200 if ready else 503)


def _run(name: str, probe: Probe) -> str:
    try:
        probe()
    except Exception:
        logger.warning("readiness probe failed: %s", name, exc_info=True)
        return "error"
    return "ok"
