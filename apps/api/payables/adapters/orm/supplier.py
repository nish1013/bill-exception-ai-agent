import uuid

from django.db import models
from django.db.models import Q

from payables.adapters.orm.tenant import Tenant

VAT_KEY = "supplier_tenant_vat_key"
NAME_KEY = "supplier_tenant_name_no_vat_key"


class SupplierRow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+")
    name = models.TextField()
    name_norm = models.TextField()
    vat_norm = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payables"
        db_table = "supplier"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "id"], name="supplier_tenant_id_key"),
            models.UniqueConstraint(
                fields=["tenant", "vat_norm"], condition=Q(vat_norm__isnull=False), name=VAT_KEY
            ),
            models.UniqueConstraint(
                fields=["tenant", "name_norm"], condition=Q(vat_norm__isnull=True), name=NAME_KEY
            ),
            models.CheckConstraint(condition=~Q(name_norm=""), name="supplier_name_norm_set"),
            models.CheckConstraint(condition=~Q(vat_norm=""), name="supplier_vat_norm_set"),
        ]
