from uuid import UUID

from pydantic import BaseModel

from app.schemas._compat import StrEnum


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    result: dict | None = None
    error_message: str | None = None
