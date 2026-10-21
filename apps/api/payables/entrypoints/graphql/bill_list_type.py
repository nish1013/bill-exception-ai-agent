import graphene

from payables.entrypoints.graphql.bill_type import BillType


class BillListType(graphene.ObjectType):
    class Meta:
        name = "BillList"

    items = graphene.List(graphene.NonNull(BillType), required=True)
    total_count = graphene.Int(required=True)
