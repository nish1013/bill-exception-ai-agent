import graphene

from payables.entrypoints.graphql.scalars import MinorUnits


class BillType(graphene.ObjectType):
    class Meta:
        name = "Bill"

    id = graphene.UUID(required=True)
    supplier_name = graphene.String(required=True)
    invoice_number = graphene.String(required=True)
    amount = MinorUnits(required=True)
    currency = graphene.String(required=True)
    issue_date = graphene.Date(required=True)
    has_receipt = graphene.Boolean(required=True)
    created_at = graphene.DateTime(required=True)


class BillListType(graphene.ObjectType):
    class Meta:
        name = "BillList"

    items = graphene.List(graphene.NonNull(BillType), required=True)
    total_count = graphene.Int(required=True)


class BillInput(graphene.InputObjectType):
    supplier_name = graphene.String(required=True)
    supplier_vat_number = graphene.String()
    invoice_number = graphene.String(required=True)
    amount = MinorUnits(required=True)
    currency = graphene.String(required=True)
    vat_amount = MinorUnits()
    issue_date = graphene.Date(required=True)
    po_number = graphene.String()
    has_receipt = graphene.Boolean(required=True)


class IngestBillPayload(graphene.ObjectType):
    bill_id = graphene.UUID(required=True)
    supplier_id = graphene.UUID(required=True)
