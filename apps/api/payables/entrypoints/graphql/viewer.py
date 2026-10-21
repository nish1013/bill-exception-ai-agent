import graphene


class Viewer(graphene.ObjectType):
    tenant_id = graphene.UUID(required=True)
    tenant_name = graphene.String()
    role = graphene.String(required=True)
