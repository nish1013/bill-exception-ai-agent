import json
import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from payables.adapters.accounting import SIGNATURE_HEADER, callback_signature
from payables.adapters.channels import ChannelsConsoleEvents
from payables.adapters.orm.proposals import ProposalSyncOrmRepository, tenant_of_sync_key
from payables.adapters.orm.tenants import tenant_transaction
from payables.adapters.readiness import PROBES, Probe
from payables.application.sync import publish_sync_changed, receive_sync_callback
from payables.domain.errors import NotFoundError, ValidationError
from payables.domain.proposals.sync import SyncCallback

logger = logging.getLogger(__name__)


@require_GET
def healthz(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


@require_GET
def readyz(request: HttpRequest) -> JsonResponse:
    results = {name: _run(name, probe) for name, probe in PROBES.items()}
    ready = all(result == "ok" for result in results.values())
    return JsonResponse(results, status=200 if ready else 503)


@require_POST
def accounting_callback(request: HttpRequest, provider: str) -> JsonResponse:
    signature = callback_signature(provider)
    if signature is None:
        return JsonResponse({"error": "NOT_FOUND"}, status=404)
    # The signature is checked before the body is read, so a forged callback writes nothing (D23).
    if not signature.valid(request.body, request.headers.get(SIGNATURE_HEADER)):
        logger.info("accounting callback refused: bad signature from %s", provider)
        return JsonResponse({"error": "UNAUTHENTICATED"}, status=401)
    try:
        callback = SyncCallback.parse(json.loads(request.body))
    except (ValueError, ValidationError):
        return JsonResponse({"error": "VALIDATION"}, status=400)
    tenant_id = tenant_of_sync_key(callback.sync_key)
    if tenant_id is None:
        return JsonResponse({"error": "NOT_FOUND"}, status=404)
    try:
        with tenant_transaction(tenant_id):
            changed = receive_sync_callback(callback, ProposalSyncOrmRepository(tenant_id))
    except NotFoundError:
        return JsonResponse({"error": "NOT_FOUND"}, status=404)
    publish_sync_changed(tenant_id, changed, ChannelsConsoleEvents())
    return JsonResponse({"status": "ok"})


def _run(name: str, probe: Probe) -> str:
    try:
        probe()
    except Exception:
        logger.warning("readiness probe failed: %s", name, exc_info=True)
        return "error"
    return "ok"
