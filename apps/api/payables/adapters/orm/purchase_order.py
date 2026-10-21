import uuid

from django.db import models

from payables.adapters.orm.money_fields import money_constraints
from payables.adapters.orm.supplier import SupplierRow
from payables.adapters.orm.tenant import Tenant

PO_NUMBER_KEY = "purchase_order_tenant_number_key"


class PurchaseOrderRow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+")
    # The migration adds the key (tenant_id, supplier_id), so both rows share a tenant (I1).
    supplier = models.ForeignKey(
        SupplierRow, on_delete=models.PROTECT, db_constraint=False, related_name="+"
    )
    po_number = models.TextField()
    po_number_norm = models.TextField()
    amount_minor = models.BigIntegerField()
    currency = models.CharField(max_length=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payables"
        db_table = "purchase_order"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "po_number_norm"], name=PO_NUMBER_KEY),
            *money_constraints("purchase_order", "amount_minor"),
        ]
