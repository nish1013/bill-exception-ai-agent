from uuid import UUID

from payables.adapters.orm.supplier import SupplierRow
from payables.application.pages import ListPage
from payables.domain.suppliers import Supplier

LIST_LIMIT = 500


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
