from uuid import UUID

from django.db import IntegrityError, transaction

from payables.adapters.orm.integrity import violated_constraint
from payables.adapters.orm.supplier import NAME_KEY, VAT_KEY, SupplierRow
from payables.domain.supplier import Supplier
from payables.domain.supplier_identity import SupplierIdentity


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


def _supplier(row: SupplierRow) -> Supplier:
    return Supplier(id=row.id, name=row.name, vat_number=row.vat_norm)
