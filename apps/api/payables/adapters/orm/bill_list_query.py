from uuid import UUID

from payables.adapters.orm.bill import BillRow
from payables.application.read.bill_list_item import BillListItem

LIST_LIMIT = 500


class BillListOrmQuery:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def latest(self) -> list[BillListItem]:
        rows = (
            BillRow.objects.filter(tenant_id=self._tenant_id)
            .order_by("-created_at", "-id")
            .values(
                "id",
                "supplier__name",
                "invoice_number",
                "amount_minor",
                "currency",
                "issue_date",
                "has_receipt",
                "created_at",
            )[:LIST_LIMIT]
        )
        return [
            BillListItem(
                id=row["id"],
                supplier_name=row["supplier__name"],
                invoice_number=row["invoice_number"],
                amount=row["amount_minor"],
                currency=row["currency"],
                issue_date=row["issue_date"],
                has_receipt=row["has_receipt"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
