from uuid import UUID

import graphene

from payables.adapters.orm.bills import BillListOrmQuery
from payables.adapters.orm.checks import CheckJobOrmRepository
from payables.adapters.orm.exceptions import InboxOrmQuery
from payables.adapters.orm.suppliers import SupplierListOrmQuery
from payables.adapters.orm.tenants import TenantRepository
from payables.application.bills import BillListItem
from payables.application.checks import get_check_job
from payables.application.exceptions import InboxFilter, InboxItem, list_exceptions
from payables.application.pages import ListPage
from payables.domain.access import Principal
from payables.domain.checks.jobs import CheckJob
from payables.domain.suppliers import Supplier
from payables.entrypoints.graphql.bill_list_type import BillListType
from payables.entrypoints.graphql.check_job_type import CheckJobType
from payables.entrypoints.graphql.exception_list_type import ExceptionListType
from payables.entrypoints.graphql.mutation import Mutation
from payables.entrypoints.graphql.supplier_list_type import SupplierListType
from payables.entrypoints.graphql.viewer import Viewer


class Query(graphene.ObjectType):
    viewer = graphene.Field(Viewer, required=True)
    bills = graphene.Field(BillListType, required=True)
    suppliers = graphene.Field(SupplierListType, required=True)
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

    def resolve_suppliers(root, info) -> ListPage[Supplier]:
        return SupplierListOrmQuery(_principal(info).tenant_id).by_name()

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
