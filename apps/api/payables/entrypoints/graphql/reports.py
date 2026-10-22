import graphene

from payables.entrypoints.graphql.scalars import MinorUnits


class CurrencyTotalType(graphene.ObjectType):
    class Meta:
        name = "CurrencyTotal"

    currency = graphene.String(required=True)
    amount = MinorUnits(required=True)


class ReportType(graphene.ObjectType):
    class Meta:
        name = "Report"

    open_exceptions = graphene.Int(required=True)
    money_at_risk = graphene.List(graphene.NonNull(CurrencyTotalType), required=True)
