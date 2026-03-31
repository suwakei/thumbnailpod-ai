from uuid import UUID

from pydantic import BaseModel, HttpUrl


class LayerInput(BaseModel):
    label: str
    s3_key: str


class PSDBuildRequest(BaseModel):
    job_id: UUID
    user_id: UUID
    base_image_url: HttpUrl
    layers: list[LayerInput]


class PSDBuildResponse(BaseModel):
    job_id: UUID
    psd_s3_key: str
