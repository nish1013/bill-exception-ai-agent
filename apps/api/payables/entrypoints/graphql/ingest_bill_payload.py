import graphene


class IngestBillPayload(graphene.ObjectType):
    bill_id = graphene.UUID(required=True)
    supplier_id = graphene.UUID(required=True)
