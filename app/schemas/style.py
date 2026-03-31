from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class StyleMetadata(BaseModel):
    color_palette: list[str] = Field(default_factory=list, description="Dominant hex colors")
    composition_features: dict = Field(default_factory=dict)
    clip_embedding: list[float] = Field(default_factory=list)


class StyleAnalyzeRequest(BaseModel):
    user_id: UUID
    image_urls: list[HttpUrl] = Field(..., min_length=1, max_length=50)


class StyleAnalyzeResponse(BaseModel):
    style_metadata: StyleMetadata


class TrainPhase(StrEnum):
    STYLE_REF = "style_ref"  # Phase 1: ControlNet style reference
    LORA = "lora"  # Phase 2: LoRA fine-tuning


class StyleTrainRequest(BaseModel):
    style_model_id: UUID
    user_id: UUID
    image_urls: list[HttpUrl] = Field(..., min_length=10, max_length=100)
    phase: TrainPhase = TrainPhase.STYLE_REF


class StyleTrainResponse(BaseModel):
    style_model_id: UUID
    job_id: str
    phase: TrainPhase
