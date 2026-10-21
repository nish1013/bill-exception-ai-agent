import uuid

from django.db import models

from payables.adapters.orm.money_fields import money_constraints
from payables.adapters.orm.supplier import SupplierRow
from payables.adapters.orm.tenant import Tenant

IDEMPOTENCY_KEY = "bill_tenant_idempotency_key"


class BillRow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+")
    # The migration adds the key (tenant_id, supplier_id), so both rows share a tenant (I1).
    supplier = models.ForeignKey(
        SupplierRow, on_delete=models.PROTECT, db_constraint=False, related_name="+"
    )
    invoice_number = models.TextField()
    invoice_number_norm = models.TextField()
    amount_minor = models.BigIntegerField()
    currency = models.CharField(max_length=3)
    vat_amount_minor = models.BigIntegerField(null=True)
    issue_date = models.DateField()
    po_number = models.TextField(null=True)
    po_number_norm = models.TextField(null=True)
    has_receipt = models.BooleanField()
    idempotency_key = models.CharField(max_length=255)
    payload_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payables"
        db_table = "bill"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "idempotency_key"], name=IDEMPOTENCY_KEY),
            models.UniqueConstraint(fields=["tenant", "id"], name="bill_tenant_id_key"),
            *money_constraints("bill", "amount_minor", "vat_amount_minor"),
        ]
        indexes = [
            models.Index(
                fields=["supplier", "invoice_number_norm"], name="bill_supplier_number_idx"
            ),
            models.Index(fields=["supplier", "amount_minor"], name="bill_supplier_amount_idx"),
        ]
