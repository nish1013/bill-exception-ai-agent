import graphene

from payables.entrypoints.graphql.supplier_type import SupplierType


class SupplierListType(graphene.ObjectType):
    class Meta:
        name = "SupplierList"

    items = graphene.List(graphene.NonNull(SupplierType), required=True)
    total_count = graphene.Int(required=True)
