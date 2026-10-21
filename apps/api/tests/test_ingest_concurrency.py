from dataclasses import replace

from payables.adapters.orm.bill_repository import BillOrmRepository
from payables.adapters.orm.outbox_repository import OutboxOrmRepository
from payables.adapters.orm.purchase_order_repository import PurchaseOrderOrmRepository
from payables.adapters.orm.supplier_repository import SupplierOrmRepository
from payables.adapters.orm.tenancy import tenant_transaction
from payables.application.bills import IngestBillCommand, ingest_bill
from payables.application.purchase_orders import AddPurchaseOrderCommand, add_purchase_order
from payables.application.suppliers import register_supplier
from payables.domain.access import Principal, Role
from payables.domain.errors import ConflictError
from tests.concurrency import owner_count, race
from tests.ingest_data import B1_PAYLOAD
from tests.tenants import T1

C1 = Principal(T1, Role.CLERK, "c1")
NEW_CO = replace(B1_PAYLOAD, supplier_name="New Co", supplier_vat_number="GB999")
NO_VAT_CO = replace(B1_PAYLOAD, supplier_name="No Vat Co", supplier_vat_number=None)


def _ingest(key: str, payload=B1_PAYLOAD):
    def call():
        return ingest_bill(
            C1,
            IngestBillCommand(key, payload),
            SupplierOrmRepository(T1),
            BillOrmRepository(T1),
        )

    return call


def test_i2_two_ingests_one_new_vat_supplier(committed_db):
    result = race(T1, _ingest("K1", NEW_CO), _ingest("K2", NEW_CO))

    assert result.errors == []
    assert result.first.supplier_id == result.second.supplier_id
    assert owner_count("supplier", "tenant_id = %s AND vat_norm = 'GB999'", [T1]) == 1
    assert owner_count("bill", "tenant_id = %s", [T1]) == 2


def test_i3_two_ingests_one_new_no_vat_supplier(committed_db):
    result = race(T1, _ingest("K1", NO_VAT_CO), _ingest("K2", NO_VAT_CO))

    assert result.errors == []
    assert result.first.supplier_id == result.second.supplier_id
    assert owner_count("supplier", "tenant_id = %s AND name_norm = 'no vat co'", [T1]) == 1
    assert owner_count("bill", "tenant_id = %s", [T1]) == 2


def test_i4_two_ingests_with_k1_one_bill(committed_db):
    with tenant_transaction(T1):
        register_supplier(
            C1, B1_PAYLOAD.supplier_name, B1_PAYLOAD.supplier_vat_number, SupplierOrmRepository(T1)
        )

    result = race(T1, _ingest("K1"), _ingest("K1"))

    assert result.errors == []
    assert result.first.id == result.second.id
    assert owner_count("bill", "tenant_id = %s AND idempotency_key = 'K1'", [T1]) == 1


def test_i5_two_adds_of_one_po_one_row(committed_db):
    with tenant_transaction(T1):
        s1 = register_supplier(C1, "Fresh Farms Ltd", "GB1", SupplierOrmRepository(T1))

    def add(number: str):
        def call():
            return add_purchase_order(
                C1,
                AddPurchaseOrderCommand(number, s1.id, 120000, "GBP"),
                SupplierOrmRepository(T1),
                PurchaseOrderOrmRepository(T1),
                OutboxOrmRepository(T1),
            )

        return call

    result = race(T1, add("PO-100"), add("po 100"))

    assert [type(error) for error in result.errors] == [ConflictError]
    assert owner_count("purchase_order", "tenant_id = %s AND po_number_norm = 'PO100'", [T1]) == 1
