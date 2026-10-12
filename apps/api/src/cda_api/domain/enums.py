from enum import StrEnum


class Role(StrEnum):
    CLINICIAN = "clinician"
    ADMIN = "admin"


class NoteStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    PROCESSING = "PROCESSING"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FAILED_VALIDATION = "FAILED_VALIDATION"


class AuditAction(StrEnum):
    NOTE_SUBMITTED = "note.submitted"
    PROCESSING_STARTED = "processing.started"
    SUMMARY_GENERATED = "summary.generated"
    PROCESSING_FAILED = "processing.failed"
    SUMMARY_EDITED = "summary.edited"
    SUMMARY_APPROVED = "summary.approved"
    SUMMARY_REJECTED = "summary.rejected"
    REGENERATION_REQUESTED = "summary.regeneration_requested"
    NOTE_EXPORTED = "note.exported"
    DATA_ERASED = "data.erased"
    RETENTION_PURGE = "data.retention_purge"
    LOGIN = "auth.login"
