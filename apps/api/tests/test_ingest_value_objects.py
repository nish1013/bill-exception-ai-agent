from dataclasses import replace

import pytest

from payables.domain.bills import BillDraft, IdempotencyKey, invoice_number
from payables.domain.errors import ValidationError
from payables.domain.money import MAX_MINOR_UNITS, Money
from payables.domain.purchase_orders import optional_po_number, po_number
from payables.domain.suppliers import SupplierIdentity, SupplierName, VatNumber
from tests.ingest_data import B1_PAYLOAD


@pytest.mark.parametrize("amount", [0, 1, 120000, MAX_MINOR_UNITS])
def test_us4_money_takes_minor_units(amount):
    assert Money(amount, "GBP").minor_units == amount


@pytest.mark.parametrize("amount", [1200.50, 1200.0, "1200", True, None, -1, MAX_MINOR_UNITS + 1])
def test_us4_money_refuses_non_minor_units(amount):
    with pytest.raises(ValidationError):
        Money(amount, "GBP")


@pytest.mark.parametrize("currency", ["XXX1", "gbp", "GB", "ZZZ", "", " GBP"])
def test_us3_money_refuses_non_iso_currency(currency):
    with pytest.raises(ValidationError):
        Money(100, currency)


@pytest.mark.parametrize("currency", ["GBP", "EUR", "USD", "JPY"])
def test_us3_money_takes_iso_currency(currency):
    assert Money(100, currency).currency == currency


@pytest.mark.parametrize(
    ("raw", "normal"),
    [("gb 123 456 789", "GB123456789"), ("GB123456789", "GB123456789"), ("gb-999.", "GB999")],
)
def test_us2_vat_normal_form(raw, normal):
    assert VatNumber.parse(raw) == VatNumber(normal)


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_us2_blank_vat_is_no_vat(raw):
    assert VatNumber.parse(raw) is None


def test_us2_vat_with_no_letter_or_digit_400():
    with pytest.raises(ValidationError):
        VatNumber.parse("--")


@pytest.mark.parametrize(
    ("first", "second"),
    [("Green Co", "GREEN CO."), ("Green  Co", " green co "), ("Café Ltd", "CAFÉ LTD")],
)
def test_us2_names_match(first, second):
    assert SupplierName.parse(first).normalised == SupplierName.parse(second).normalised


@pytest.mark.parametrize(
    ("first", "second"), [("Green Co", "Green Co Ltd"), ("Fresh Farms Ltd", "Fresh Farms Limited")]
)
def test_us2_legal_suffix_kept(first, second):
    assert SupplierName.parse(first).normalised != SupplierName.parse(second).normalised


@pytest.mark.parametrize("raw", ["", "   ", "..."])
def test_us2_empty_name_400(raw):
    with pytest.raises(ValidationError):
        SupplierName.parse(raw)


def test_us2_identity_keeps_display_name():
    identity = SupplierIdentity.parse("  Fresh Farms Ltd ", "gb 123 456 789")

    assert identity.name.raw == "Fresh Farms Ltd"
    assert identity.vat == VatNumber("GB123456789")


@pytest.mark.parametrize("raw", ["INV-001", "inv 001", "Inv/001", "INV001"])
def test_us4_invoice_number_normal_form(raw):
    assert invoice_number(raw).normalised == "INV001"


def test_us3_po_number_normal_form():
    assert po_number("po 100").normalised == po_number("PO-100").normalised == "PO100"


@pytest.mark.parametrize("raw", ["", " ", "-/-"])
def test_us4_invoice_number_empty_400(raw):
    with pytest.raises(ValidationError):
        invoice_number(raw)


@pytest.mark.parametrize("raw", [None, "", "  "])
def test_us4_blank_po_number_is_no_po(raw):
    assert optional_po_number(raw) is None


@pytest.mark.parametrize("key", ["K1", " ", "k" * 255])
def test_us4_idempotency_key_valid(key):
    assert IdempotencyKey(key).value == key


@pytest.mark.parametrize("key", ["", "k" * 256, "K\n1", "\t"])
def test_us4_idempotency_key_refused(key):
    with pytest.raises(ValidationError):
        IdempotencyKey(key)


def test_d26_same_payload_same_hash():
    copy = replace(B1_PAYLOAD)

    assert copy.digest() == B1_PAYLOAD.digest()


@pytest.mark.parametrize(
    "change",
    [
        {"invoice_number": "inv 001"},
        {"amount": 120001},
        {"vat_amount": None},
        {"po_number": None},
        {"has_receipt": False},
        {"supplier_vat_number": "gb 123 456 789"},
    ],
)
def test_d26_other_payload_other_hash(change):
    changed = replace(B1_PAYLOAD, **change)

    assert changed.digest() != B1_PAYLOAD.digest()


def test_us4_draft_normalises_b1():
    draft = BillDraft.parse(B1_PAYLOAD)

    assert draft.invoice_number.normalised == "INV001"
    assert draft.amount == Money(120000, "GBP")
    assert draft.vat_amount == Money(20000, "GBP")
    assert draft.po_number.normalised == "PO100"
    assert draft.supplier.vat == VatNumber("GB123456789")


def test_us4_draft_refuses_float_vat():
    payload = replace(B1_PAYLOAD, vat_amount=200.5)

    with pytest.raises(ValidationError):
        BillDraft.parse(payload)
