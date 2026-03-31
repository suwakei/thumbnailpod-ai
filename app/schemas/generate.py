from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class GenerationEngine(StrEnum):
    DALLE3 = "dalle3"
    SDXL = "sdxl"


class GenerateRequest(BaseModel):
    job_id: UUID
    user_id: UUID
    prompt: str = Field(..., min_length=1, max_length=2000)
    engine: GenerationEngine = GenerationEngine.DALLE3
    style_model_id: UUID | None = None
    negative_prompt: str | None = None
    width: int = 1280
    height: int = 720


class GenerateResponse(BaseModel):
    job_id: UUID
    s3_key: str
    width: int
    height: int
