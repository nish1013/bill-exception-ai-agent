import graphene

from payables.application.proposals import (
    ProposalActionItem,
    ProposalExceptionItem,
    ProposalItem,
)


class ProposalExceptionType(graphene.ObjectType):
    class Meta:
        name = "ProposalException"

    id = graphene.UUID(required=True)
    rule = graphene.String(required=True)
    invoice_number = graphene.String(required=True)

    def resolve_rule(root: ProposalExceptionItem, info) -> str:
        return root.rule.value


class ProposalActionType(graphene.ObjectType):
    class Meta:
        name = "ProposalAction"

    kind = graphene.String(required=True)
    bill_id = graphene.UUID(required=True)
    supplier_name = graphene.String(required=True)
    invoice_number = graphene.String(required=True)
    po_number = graphene.String()

    def resolve_kind(root: ProposalActionItem, info) -> str:
        return root.kind.value


class ProposalType(graphene.ObjectType):
    class Meta:
        name = "Proposal"

    id = graphene.UUID(required=True)
    status = graphene.String(required=True)
    requested_by = graphene.String(required=True)
    quota_slot = graphene.Int(required=True)
    failed_reason = graphene.String()
    approved_by = graphene.String()
    approved_at = graphene.DateTime()
    reject_reason = graphene.String()
    created_at = graphene.DateTime(required=True)
    exceptions = graphene.List(graphene.NonNull(ProposalExceptionType), required=True)
    actions = graphene.List(graphene.NonNull(ProposalActionType), required=True)

    def resolve_status(root: ProposalItem, info) -> str:
        return root.status.value

    def resolve_failed_reason(root: ProposalItem, info) -> str | None:
        return None if root.failed_reason is None else root.failed_reason.value


class ProposalListType(graphene.ObjectType):
    class Meta:
        name = "ProposalList"

    items = graphene.List(graphene.NonNull(ProposalType), required=True)
    total_count = graphene.Int(required=True)
