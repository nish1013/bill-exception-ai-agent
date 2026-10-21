import graphene

from payables.entrypoints.graphql.exception_type import ExceptionType


class ExceptionListType(graphene.ObjectType):
    class Meta:
        name = "ExceptionList"

    items = graphene.List(graphene.NonNull(ExceptionType), required=True)
    total_count = graphene.Int(required=True)
