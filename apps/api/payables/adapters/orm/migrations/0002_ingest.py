import uuid

import django.db.models.deletion
from django.db import migrations, models

from payables.adapters.orm.row_level_security import tenant_isolation

READ_AND_INSERT = "SELECT, INSERT"


def tenant_supplier_key(table: str) -> migrations.RunSQL:
    return migrations.RunSQL(
        f"ALTER TABLE {table} ADD CONSTRAINT {table}_tenant_supplier_fkey "
        "FOREIGN KEY (tenant_id, supplier_id) REFERENCES supplier (tenant_id, id)",
        f"ALTER TABLE {table} DROP CONSTRAINT {table}_tenant_supplier_fkey",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("payables", "0001_tenant"),
    ]

    operations = [
        migrations.CreateModel(
            name="SupplierRow",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ("name", models.TextField()),
                ("name_norm", models.TextField()),
                ("vat_norm", models.TextField(null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="payables.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "supplier",
            },
        ),
        migrations.CreateModel(
            name="PurchaseOrderRow",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ("po_number", models.TextField()),
                ("po_number_norm", models.TextField()),
                ("amount_minor", models.BigIntegerField()),
                ("currency", models.CharField(max_length=3)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="payables.tenant",
                    ),
                ),
                (
                    "supplier",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="payables.supplierrow",
                    ),
                ),
            ],
            options={
                "db_table": "purchase_order",
            },
        ),
        migrations.CreateModel(
            name="BillRow",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ("invoice_number", models.TextField()),
                ("invoice_number_norm", models.TextField()),
                ("amount_minor", models.BigIntegerField()),
                ("currency", models.CharField(max_length=3)),
                ("vat_amount_minor", models.BigIntegerField(null=True)),
                ("issue_date", models.DateField()),
                ("po_number", models.TextField(null=True)),
                ("po_number_norm", models.TextField(null=True)),
                ("has_receipt", models.BooleanField()),
                ("idempotency_key", models.CharField(max_length=255)),
                ("payload_hash", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="payables.tenant",
                    ),
                ),
                (
                    "supplier",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="payables.supplierrow",
                    ),
                ),
            ],
            options={
                "db_table": "bill",
            },
        ),
        migrations.AddConstraint(
            model_name="supplierrow",
            constraint=models.UniqueConstraint(
                fields=("tenant", "id"), name="supplier_tenant_id_key"
            ),
        ),
        migrations.AddConstraint(
            model_name="supplierrow",
            constraint=models.UniqueConstraint(
                condition=models.Q(("vat_norm__isnull", False)),
                fields=("tenant", "vat_norm"),
                name="supplier_tenant_vat_key",
            ),
        ),
        migrations.AddConstraint(
            model_name="supplierrow",
            constraint=models.UniqueConstraint(
                condition=models.Q(("vat_norm__isnull", True)),
                fields=("tenant", "name_norm"),
                name="supplier_tenant_name_no_vat_key",
            ),
        ),
        migrations.AddConstraint(
            model_name="supplierrow",
            constraint=models.CheckConstraint(
                condition=models.Q(("name_norm", ""), _negated=True), name="supplier_name_norm_set"
            ),
        ),
        migrations.AddConstraint(
            model_name="supplierrow",
            constraint=models.CheckConstraint(
                condition=models.Q(("vat_norm", ""), _negated=True), name="supplier_vat_norm_set"
            ),
        ),
        migrations.AddConstraint(
            model_name="purchaseorderrow",
            constraint=models.UniqueConstraint(
                fields=("tenant", "po_number_norm"), name="purchase_order_tenant_number_key"
            ),
        ),
        migrations.AddConstraint(
            model_name="purchaseorderrow",
            constraint=models.CheckConstraint(
                condition=models.Q(("currency__regex", "^[A-Z]{3}$")),
                name="purchase_order_currency_iso",
            ),
        ),
        migrations.AddConstraint(
            model_name="purchaseorderrow",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount_minor__gte", 0)),
                name="purchase_order_amount_minor_not_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="billrow",
            constraint=models.UniqueConstraint(
                fields=("tenant", "idempotency_key"), name="bill_tenant_idempotency_key"
            ),
        ),
        migrations.AddConstraint(
            model_name="billrow",
            constraint=models.CheckConstraint(
                condition=models.Q(("currency__regex", "^[A-Z]{3}$")), name="bill_currency_iso"
            ),
        ),
        migrations.AddConstraint(
            model_name="billrow",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount_minor__gte", 0)), name="bill_amount_minor_not_negative"
            ),
        ),
        migrations.AddConstraint(
            model_name="billrow",
            constraint=models.CheckConstraint(
                condition=models.Q(("vat_amount_minor__gte", 0)),
                name="bill_vat_amount_minor_not_negative",
            ),
        ),
        tenant_supplier_key("purchase_order"),
        tenant_supplier_key("bill"),
        # Suppliers, POs and bills never change after ingest (D31). The app role only adds rows.
        tenant_isolation("supplier", privileges=READ_AND_INSERT),
        tenant_isolation("purchase_order", privileges=READ_AND_INSERT),
        tenant_isolation("bill", privileges=READ_AND_INSERT),
    ]
