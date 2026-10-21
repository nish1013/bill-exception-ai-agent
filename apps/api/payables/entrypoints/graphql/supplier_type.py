import graphene


class SupplierType(graphene.ObjectType):
    class Meta:
        name = "Supplier"

    id = graphene.UUID(required=True)
    name = graphene.String(required=True)
    vat_number = graphene.String()
