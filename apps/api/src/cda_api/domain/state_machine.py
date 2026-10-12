from cda_api.domain.enums import NoteStatus
from cda_api.domain.errors import InvalidTransition

S = NoteStatus

# Review workflow. APPROVED and REJECTED are terminal: only an approved summary is final.
# Regeneration and retry both go back to SUBMITTED so the pipeline picks the note up again.
_ALLOWED: dict[NoteStatus, frozenset[NoteStatus]] = {
    S.SUBMITTED: frozenset({S.PROCESSING}),
    S.PROCESSING: frozenset({S.PENDING_REVIEW, S.FAILED_VALIDATION}),
    S.PENDING_REVIEW: frozenset({S.APPROVED, S.REJECTED, S.SUBMITTED}),
    S.FAILED_VALIDATION: frozenset({S.SUBMITTED}),
    S.APPROVED: frozenset(),
    S.REJECTED: frozenset(),
}

TERMINAL = frozenset({S.APPROVED, S.REJECTED})


def can_transition(current: NoteStatus, target: NoteStatus) -> bool:
    return target in _ALLOWED[current]


def ensure_transition(current: NoteStatus, target: NoteStatus) -> NoteStatus:
    if not can_transition(current, target):
        raise InvalidTransition(current.value, target.value)
    return target
