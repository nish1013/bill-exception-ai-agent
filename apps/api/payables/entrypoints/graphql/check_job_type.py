import graphene

from payables.domain.checks.check_job import CheckJob


class CheckJobType(graphene.ObjectType):
    class Meta:
        name = "CheckJob"

    id = graphene.UUID(required=True)
    status = graphene.String(required=True)
    bill_count = graphene.Int(required=True)
    ok_count = graphene.Int(required=True)
    failed_count = graphene.Int(required=True)
    seq = graphene.Int(required=True)
    percent = graphene.Int(required=True)

    def resolve_status(root: CheckJob, info) -> str:
        return root.status.value
