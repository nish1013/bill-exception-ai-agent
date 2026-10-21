import graphene

from payables.application.read.inbox_item import InboxItem


class ExceptionType(graphene.ObjectType):
    class Meta:
        name = "Exception"

    id = graphene.UUID(required=True)
    bill_id = graphene.UUID(required=True)
    supplier_name = graphene.String(required=True)
    invoice_number = graphene.String(required=True)
    rule = graphene.String(required=True)
    severity = graphene.String(required=True)
    status = graphene.String(required=True)
    related_bill_id = graphene.UUID()
    created_at = graphene.DateTime(required=True)
    resolved_by = graphene.String()
    reason = graphene.String()

    def resolve_rule(root: InboxItem, info) -> str:
        return root.rule.value

    def resolve_severity(root: InboxItem, info) -> str:
        return root.severity.value

    def resolve_status(root: InboxItem, info) -> str:
        return root.status.value
