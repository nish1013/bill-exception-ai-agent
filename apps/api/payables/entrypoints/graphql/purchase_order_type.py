import graphene

from payables.domain.purchase_orders import PurchaseOrder
from payables.entrypoints.graphql.minor_units import MinorUnits


class PurchaseOrderType(graphene.ObjectType):
    class Meta:
        name = "PurchaseOrder"

    id = graphene.UUID(required=True)
    po_number = graphene.String(required=True)
    supplier_id = graphene.UUID(required=True)
    amount = MinorUnits(required=True)
    currency = graphene.String(required=True)

    def resolve_amount(root: PurchaseOrder, info) -> int:
        return root.amount.minor_units

    def resolve_currency(root: PurchaseOrder, info) -> str:
        return root.amount.currency
