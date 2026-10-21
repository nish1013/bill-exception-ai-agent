from uuid import UUID

import graphene

from payables.adapters.orm.bill_list_query import BillListOrmQuery
from payables.adapters.orm.check_job_repository import CheckJobOrmRepository
from payables.adapters.orm.inbox_query import InboxOrmQuery
from payables.adapters.orm.tenant_repository import TenantRepository
from payables.application.read.bill_list_item import BillListItem
from payables.application.read.get_check_job import get_check_job
from payables.application.read.inbox_filter import InboxFilter
from payables.application.read.inbox_item import InboxItem
from payables.application.read.list_exceptions import list_exceptions
from payables.application.read.list_page import ListPage
from payables.domain.checks.check_job import CheckJob
from payables.domain.principal import Principal
from payables.entrypoints.graphql.bill_list_type import BillListType
from payables.entrypoints.graphql.check_job_type import CheckJobType
from payables.entrypoints.graphql.exception_list_type import ExceptionListType
from payables.entrypoints.graphql.mutation import Mutation
from payables.entrypoints.graphql.viewer import Viewer


class Query(graphene.ObjectType):
    viewer = graphene.Field(Viewer, required=True)
    bills = graphene.Field(BillListType, required=True)
    exceptions = graphene.Field(
        ExceptionListType,
        required=True,
        status=graphene.String(),
        severity=graphene.String(),
    )
    check_job = graphene.Field(CheckJobType, required=True, id=graphene.UUID(required=True))

    def resolve_viewer(root, info) -> Viewer:
        principal = _principal(info)
        return Viewer(
            tenant_id=principal.tenant_id,
            tenant_name=TenantRepository().find_name(principal.tenant_id),
            role=principal.role.value,
        )

    def resolve_bills(root, info) -> ListPage[BillListItem]:
        return BillListOrmQuery(_principal(info).tenant_id).latest()

    def resolve_exceptions(
        root, info, status: str | None = None, severity: str | None = None
    ) -> ListPage[InboxItem]:
        inbox = InboxOrmQuery(_principal(info).tenant_id)
        return list_exceptions(InboxFilter.parse(status, severity), inbox)

    def resolve_check_job(root, info, id: UUID) -> CheckJob:
        return get_check_job(id, CheckJobOrmRepository(_principal(info).tenant_id))


def _principal(info) -> Principal:
    return info.context.principal


schema = graphene.Schema(query=Query, mutation=Mutation)
