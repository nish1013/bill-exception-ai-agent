import hashlib
import hmac
import json
import urllib.request
from typing import Protocol
from uuid import UUID

from celery import Celery
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction

from payables.adapters.broker import APPLY, STUB_CALLBACK_TASK
from payables.adapters.orm.accounting import STUB_MODES, StubLedgerRow, StubModeRow
from payables.adapters.orm.tenants import tenant_transaction
from payables.application.sync import AccountingSyncPort, AccountingUnavailableError
from payables.domain.proposals.sync import CallbackStatus, SyncAction, SyncAnswer

STUB = "stub"
SIGNATURE_HEADER = "X-Accounting-Signature"
SIGNATURE_PREFIX = "sha256="
CALLBACK_DELAY_SECONDS = 2
CALLBACK_TIMEOUT_SECONDS = 5

MODE_ANSWERS = {"ok": SyncAnswer.SYNCED, "callback": SyncAnswer.ACCEPTED}


class CallbackScheduler(Protocol):
    def schedule(self, sync_key: UUID) -> None: ...


class CallbackSignature:
    """HMAC-SHA256 of the raw body with the provider's shared secret (D23)."""

    def __init__(self, secret: str) -> None:
        if not secret:
            raise ImproperlyConfigured("a callback signature needs a secret")
        self._secret = secret.encode()

    def sign(self, body: bytes) -> str:
        digest = hmac.new(self._secret, body, hashlib.sha256).hexdigest()
        return f"{SIGNATURE_PREFIX}{digest}"

    def valid(self, body: bytes, signature: str | None) -> bool:
        return signature is not None and hmac.compare_digest(self.sign(body), signature)


class StubAccounting:
    """The demo accounting system (D51). Its mode sets the answer: ok, fail or callback."""

    def __init__(self, callbacks: CallbackScheduler, default_mode: str) -> None:
        self._callbacks = callbacks
        self._default_mode = default_mode

    def send(self, action: SyncAction) -> SyncAnswer:
        with tenant_transaction(action.tenant_id):
            mode = self._mode(action.tenant_id)
            if mode not in MODE_ANSWERS:
                raise AccountingUnavailableError("the accounting stub is in fail mode")
            answer, received = self._receive(action, MODE_ANSWERS[mode])
        if received and answer is SyncAnswer.ACCEPTED:
            self._callbacks.schedule(action.sync_key)
        return answer

    def _mode(self, tenant_id: UUID) -> str:
        row = StubModeRow.objects.filter(tenant_id=tenant_id).values_list("mode", flat=True)
        return row.first() or self._default_mode

    def _receive(self, action: SyncAction, answer: SyncAnswer) -> tuple[SyncAnswer, bool]:
        try:
            with transaction.atomic():
                StubLedgerRow.objects.create(
                    sync_key=action.sync_key,
                    tenant_id=action.tenant_id,
                    kind=action.kind.value,
                    bill_id=action.bill_id,
                    supplier_name=action.supplier_name,
                    invoice_number=action.invoice_number,
                    po_number=action.po_number,
                    answer=answer.value,
                )
        except IntegrityError:
            # A known key: the stub posts nothing new and gives its first answer (D8).
            stored = StubLedgerRow.objects.get(sync_key=action.sync_key)
            return SyncAnswer(stored.answer), False
        return answer, True


class CeleryCallbackScheduler:
    def __init__(self, app: Celery) -> None:
        self._app = app

    def schedule(self, sync_key: UUID) -> None:
        self._app.send_task(
            STUB_CALLBACK_TASK,
            kwargs={"sync_key": str(sync_key)},
            queue=APPLY,
            countdown=CALLBACK_DELAY_SECONDS,
        )


def accounting_from_settings(app: Celery) -> AccountingSyncPort:
    # The demo stub is the only adapter in v1 (D51).
    if settings.ACCOUNTING_STUB_MODE not in STUB_MODES:
        raise ImproperlyConfigured(
            f"ACCOUNTING_STUB_MODE {settings.ACCOUNTING_STUB_MODE!r} is not known"
        )
    return StubAccounting(CeleryCallbackScheduler(app), settings.ACCOUNTING_STUB_MODE)


def callback_signature(provider: str) -> CallbackSignature | None:
    if provider != STUB:
        return None
    return CallbackSignature(settings.ACCOUNTING_CALLBACK_SECRET)


def callback_body(sync_key: UUID) -> bytes:
    body = {"sync_key": str(sync_key), "status": CallbackStatus.SUCCEEDED.value}
    return json.dumps(body).encode()


def send_stub_callback(sync_key: UUID) -> None:
    body = callback_body(sync_key)
    request = urllib.request.Request(
        settings.ACCOUNTING_CALLBACK_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            SIGNATURE_HEADER: CallbackSignature(settings.ACCOUNTING_CALLBACK_SECRET).sign(body),
        },
    )
    urllib.request.urlopen(request, timeout=CALLBACK_TIMEOUT_SECONDS).close()
