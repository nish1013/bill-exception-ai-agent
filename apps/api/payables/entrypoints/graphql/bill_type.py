import graphene

from payables.entrypoints.graphql.minor_units import MinorUnits


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
