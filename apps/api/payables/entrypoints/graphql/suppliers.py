import graphene


class SupplierType(graphene.ObjectType):
    class Meta:
        name = "Supplier"

    id = graphene.UUID(required=True)
    name = graphene.String(required=True)
    vat_number = graphene.String()


class SupplierListType(graphene.ObjectType):
    class Meta:
        name = "SupplierList"

    items = graphene.List(graphene.NonNull(SupplierType), required=True)
    total_count = graphene.Int(required=True)
