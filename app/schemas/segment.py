from uuid import UUID

from pydantic import BaseModel, HttpUrl


class SegmentRequest(BaseModel):
    job_id: UUID
    image_url: HttpUrl


class Layer(BaseModel):
    label: str
    s3_key: str


class SegmentResponse(BaseModel):
    job_id: UUID
    layers: list[Layer]
    psd_s3_key: str | None = None
