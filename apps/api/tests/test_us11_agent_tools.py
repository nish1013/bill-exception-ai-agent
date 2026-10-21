from datetime import date
from uuid import UUID

import pytest

from payables.domain.proposals.agent import (
    MAX_SECONDS,
    MAX_TOOL_CALLS,
    AgentRun,
    AgentTools,
    ProposalScope,
    ScopeBill,
    ScopeException,
    ScopePurchaseOrder,
    ToolCall,
    ToolOutcome,
)
from payables.domain.proposals.proposals import ActionKind, DraftAction, FailedReason

P1 = UUID(int=1)
E1 = UUID(int=11)
B1 = UUID(int=101)
B2 = UUID(int=102)
B3_OUTSIDE = UUID(int=103)


def _bill(bill_id: UUID, invoice_number: str) -> ScopeBill:
    return ScopeBill(
        id=bill_id,
        supplier_name="Fresh Farms Ltd",
        invoice_number=invoice_number,
        amount_minor=120000,
        currency="GBP",
        vat_amount_minor=20000,
        issue_date=date(2026, 10, 1),
        po_number="PO-100",
        has_receipt=True,
    )


SCOPE = ProposalScope(
    proposal_id=P1,
    exceptions=[ScopeException(E1, "duplicate", B2, B1)],
    bills={B1: _bill(B1, "INV-001"), B2: _bill(B2, "inv 001")},
    purchase_orders={"PO100": ScopePurchaseOrder("PO-100", 120000, "GBP")},
)


def _run(name: str, **arguments) -> tuple[ToolOutcome, DraftAction | None]:
    result = AgentTools(SCOPE).run(ToolCall("c", name, arguments))
    return result.outcome, result.action


@pytest.mark.parametrize(
    ("name", "arguments", "outcome", "action"),
    [
        ("list_exceptions", {}, ToolOutcome.DONE, None),
        ("lookup_bill", {"bill_id": str(B2)}, ToolOutcome.DONE, None),
        ("lookup_po", {"po_number": "po 100"}, ToolOutcome.DONE, None),
        ("draft_hold", {"bill_id": str(B2)}, ToolOutcome.DONE, DraftAction(ActionKind.HOLD, B2)),
        (
            "draft_credit",
            {"bill_id": str(B1)},
            ToolOutcome.DONE,
            DraftAction(ActionKind.CREDIT, B1),
        ),
        (
            "draft_match",
            {"bill_id": str(B1), "po_number": "PO-100"},
            ToolOutcome.DONE,
            DraftAction(ActionKind.MATCH, B1, "PO-100"),
        ),
        ("draft_match", {"bill_id": str(B1), "po_number": "PO-999"}, ToolOutcome.INVALID, None),
        ("lookup_po", {"po_number": "PO-999"}, ToolOutcome.INVALID, None),
        ("lookup_bill", {"bill_id": str(B3_OUTSIDE)}, ToolOutcome.INVALID, None),
        ("draft_hold", {"bill_id": str(B3_OUTSIDE)}, ToolOutcome.INVALID, None),
        ("draft_hold", {"bill_id": "not-a-uuid"}, ToolOutcome.INVALID, None),
        ("draft_hold", {}, ToolOutcome.INVALID, None),
        ("approve_proposal", {"proposal_id": str(P1)}, ToolOutcome.REFUSED, None),
        ("apply_proposal", {}, ToolOutcome.REFUSED, None),
        ("update_bill", {"bill_id": str(B2)}, ToolOutcome.REFUSED, None),
    ],
)
def test_us11_tool_allowlist_and_scope(name, arguments, outcome, action):
    assert _run(name, **arguments) == (outcome, action)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.mark.parametrize(("elapsed", "timed_out"), [(59.9, False), (60.0, True), (61.0, True)])
def test_us11_run_times_out_at_60_s(elapsed, timed_out):
    clock = FakeClock()
    run = AgentRun.start(clock)
    clock.now += elapsed

    assert run.timed_out is timed_out
    assert MAX_SECONDS == 60.0


def test_us11_eight_calls_allowed_then_none_left():
    run = AgentRun.start(FakeClock())
    result = AgentTools(SCOPE).run(ToolCall("c", "list_exceptions", {}))
    for _ in range(MAX_TOOL_CALLS):
        assert run.has_call_left()
        run.record_call(ToolCall("c", "list_exceptions", {}), result)

    assert MAX_TOOL_CALLS == 8
    assert not run.has_call_left()


def test_us11_same_draft_twice_gives_one_action():
    run = AgentRun.start(FakeClock())
    call = ToolCall("c", "draft_hold", {"bill_id": str(B2)})
    for _ in range(2):
        run.record_call(call, AgentTools(SCOPE).run(call))

    assert run.finish().actions == [DraftAction(ActionKind.HOLD, B2)]


def test_us11_no_action_drafted_fails_with_no_actions():
    outcome = AgentRun.start(FakeClock()).finish()

    assert (outcome.actions, outcome.failed_reason) == ([], FailedReason.NO_ACTIONS)


def test_us11_failed_run_keeps_no_actions():
    run = AgentRun.start(FakeClock())
    call = ToolCall("c", "draft_hold", {"bill_id": str(B2)})
    run.record_call(call, AgentTools(SCOPE).run(call))

    outcome = run.fail(FailedReason.TIMEOUT)

    assert (outcome.actions, outcome.failed_reason) == ([], FailedReason.TIMEOUT)
