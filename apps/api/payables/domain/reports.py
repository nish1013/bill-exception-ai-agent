from payables.domain.checks.exceptions import ExceptionStatus

# A bill is at risk until accounting has the fix of its exception (D10, D13).
AT_RISK_STATUSES: tuple[ExceptionStatus, ...] = (
    ExceptionStatus.OPEN,
    ExceptionStatus.PENDING_SYNC,
)
