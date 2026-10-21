import uuid
from uuid import UUID

from django.db import IntegrityError, models, transaction
from django.db.models import Q

from payables.adapters.orm.constraints import violated_constraint
from payables.adapters.orm.tenants import Tenant
from payables.application.pages import ListPage
from payables.domain.suppliers import Supplier, SupplierIdentity

VAT_KEY = "supplier_tenant_vat_key"
NAME_KEY = "supplier_tenant_name_no_vat_key"
LIST_LIMIT = 500


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


class SupplierOrmRepository:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def find_or_add(self, identity: SupplierIdentity) -> Supplier:
        found = self._find(identity)
        if found is not None:
            return found
        try:
            with transaction.atomic():
                row = SupplierRow.objects.create(
                    tenant_id=self._tenant_id,
                    name=identity.name.raw,
                    name_norm=identity.name.normalised,
                    vat_norm=identity.vat.normalised if identity.vat else None,
                )
        except IntegrityError as error:
            # A concurrent ingest added the same supplier first (I2, I3). Its row is now committed.
            found = (
                self._find(identity) if violated_constraint(error) in (VAT_KEY, NAME_KEY) else None
            )
            if found is None:
                raise
            return found
        return _supplier(row)

    def exists(self, supplier_id: UUID) -> bool:
        return SupplierRow.objects.filter(tenant_id=self._tenant_id, id=supplier_id).exists()

    def _find(self, identity: SupplierIdentity) -> Supplier | None:
        rows = SupplierRow.objects.filter(tenant_id=self._tenant_id)
        if identity.vat is not None:
            rows = rows.filter(vat_norm=identity.vat.normalised)
        else:
            rows = rows.filter(vat_norm__isnull=True, name_norm=identity.name.normalised)
        row = rows.order_by("created_at").first()
        return None if row is None else _supplier(row)


class SupplierListOrmQuery:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def by_name(self) -> ListPage[Supplier]:
        suppliers = SupplierRow.objects.filter(tenant_id=self._tenant_id)
        rows = suppliers.order_by("name_norm", "id").values("id", "name", "vat_norm")[:LIST_LIMIT]
        items = [
            Supplier(id=row["id"], name=row["name"], vat_number=row["vat_norm"]) for row in rows
        ]
        return ListPage(items=items, total_count=suppliers.count())


def _supplier(row: SupplierRow) -> Supplier:
    return Supplier(id=row.id, name=row.name, vat_number=row.vat_norm)
