import graphene

from payables.adapters.orm.tenant_repository import TenantRepository
from payables.entrypoints.graphql.mutation import Mutation
from payables.entrypoints.graphql.viewer import Viewer


class Query(graphene.ObjectType):
    viewer = graphene.Field(Viewer, required=True)

    def resolve_viewer(root, info) -> Viewer:
        principal = info.context.principal
        return Viewer(
            tenant_id=principal.tenant_id,
            tenant_name=TenantRepository().find_name(principal.tenant_id),
            role=principal.role.value,
        )


schema = graphene.Schema(query=Query, mutation=Mutation)
