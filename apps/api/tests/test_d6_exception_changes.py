from uuid import UUID

import pytest

from payables.domain.checks.exception_changes import changes_after_check
from payables.domain.checks.finding import Finding
from payables.domain.checks.resolution_kind import ResolutionKind
from payables.domain.checks.rule import Rule
from payables.domain.checks.stored_exception import StoredException

E1 = UUID(int=1)
B1 = UUID(int=101)
FOUND = Finding.repeat_of(Rule.DUPLICATE, B1)


def _stored(resolution: ResolutionKind | None, fingerprint: str = str(B1)) -> StoredException:
    return StoredException(E1, Rule.DUPLICATE, fingerprint, resolution)


@pytest.mark.parametrize(
    ("found", "resolution", "resolve", "reopen"),
    [
        ([FOUND], None, [], []),
        ([], None, [E1], []),
        ([FOUND], ResolutionKind.SYSTEM, [], [E1]),
        ([], ResolutionKind.SYSTEM, [], []),
        ([FOUND], ResolutionKind.IGNORE, [], []),
        ([], ResolutionKind.IGNORE, [], []),
    ],
)
def test_d6_changes_after_check(found, resolution, resolve, reopen):
    changes = changes_after_check(found, [_stored(resolution)])

    assert (changes.to_resolve, changes.to_reopen) == (resolve, reopen)


def test_d6_other_fingerprint_is_another_problem():
    changes = changes_after_check([FOUND], [_stored(None, fingerprint=str(UUID(int=102)))])

    assert changes.to_resolve == [E1]


def test_d6_other_rule_is_another_problem():
    found = [Finding.repeat_of(Rule.POSSIBLE_DUPLICATE, B1)]

    assert changes_after_check(found, [_stored(None)]).to_resolve == [E1]
