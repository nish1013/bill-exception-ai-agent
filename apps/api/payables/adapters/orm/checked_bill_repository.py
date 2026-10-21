from datetime import timedelta
from uuid import UUID

from django.db.models import Q

from payables.adapters.orm.bill import BillRow
from payables.domain.checks.checked_bill import CheckedBill
from payables.domain.checks.duplicate_rules import POSSIBLE_DUPLICATE_WINDOW_DAYS
from payables.domain.errors import NotFoundError
from payables.domain.money import Money

FIELDS = (
    "id",
    "supplier_id",
    "invoice_number_norm",
    "amount_minor",
    "currency",
    "issue_date",
    "created_at",
)


class CheckedBillOrmRepository:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def existing_ids(self, bill_ids: list[UUID]) -> set[UUID]:
        return set(self._rows().filter(id__in=bill_ids).values_list("id", flat=True))

    def get(self, bill_id: UUID) -> CheckedBill:
        row = self._rows().filter(id=bill_id).values(*FIELDS).first()
        if row is None:
            raise NotFoundError("bill not found")
        return _checked_bill(row)

    def earlier_alike(self, bill: CheckedBill) -> list[CheckedBill]:
        window = timedelta(days=POSSIBLE_DUPLICATE_WINDOW_DAYS)
        earlier = Q(created_at__lt=bill.ingested_at) | Q(
            created_at=bill.ingested_at, id__lt=bill.id
        )
        alike = Q(invoice_number_norm=bill.invoice_number) | Q(
            amount_minor=bill.amount.minor_units,
            currency=bill.amount.currency,
            issue_date__range=(bill.issue_date - window, bill.issue_date + window),
        )
        rows = self._rows().filter(earlier, alike, supplier_id=bill.supplier_id).values(*FIELDS)
        return [_checked_bill(row) for row in rows]

    def _rows(self):
        return BillRow.objects.filter(tenant_id=self._tenant_id)


def _checked_bill(row: dict) -> CheckedBill:
    return CheckedBill(
        id=row["id"],
        supplier_id=row["supplier_id"],
        invoice_number=row["invoice_number_norm"],
        amount=Money(row["amount_minor"], row["currency"]),
        issue_date=row["issue_date"],
        ingested_at=row["created_at"],
    )
