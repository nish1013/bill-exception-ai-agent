import graphene

from payables.application.sync import LedgerEntry


class LedgerEntryType(graphene.ObjectType):
    class Meta:
        name = "LedgerEntry"

    sync_key = graphene.UUID(required=True)
    kind = graphene.String(required=True)
    supplier_name = graphene.String(required=True)
    invoice_number = graphene.String(required=True)
    po_number = graphene.String()
    answer = graphene.String(required=True)
    received_at = graphene.DateTime(required=True)

    def resolve_kind(root: LedgerEntry, info) -> str:
        return root.kind.value

    def resolve_answer(root: LedgerEntry, info) -> str:
        return root.answer.value


class LedgerListType(graphene.ObjectType):
    class Meta:
        name = "LedgerList"

    items = graphene.List(graphene.NonNull(LedgerEntryType), required=True)
    total_count = graphene.Int(required=True)
