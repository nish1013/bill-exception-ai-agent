import graphene

from payables.entrypoints.graphql.minor_units import MinorUnits


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
