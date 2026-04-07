"""Pydantic schemas for thumbnail editing."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class EditOperationType(StrEnum):
    TEXT_CHANGE = "text_change"
    COLOR_ADJUST = "color_adjust"
    MOVE = "move"


class Position(BaseModel):
    x: int
    y: int


class EditOperation(BaseModel):
    type: EditOperationType
    layer: str
    content: str | None = None
    position: Position | None = None
    brightness: float | None = None
    contrast: float | None = None
    saturation: float | None = None


class EditRequest(BaseModel):
    job_id: UUID
    user_id: UUID
    original_layers: dict[str, str] = Field(..., description="label -> s3_key mapping")
    operations: list[EditOperation] = Field(..., min_length=1)


class EditResponse(BaseModel):
    job_id: UUID
    layers: dict[str, str] = Field(..., description="Updated layers: label -> s3_key")
    unchanged_layers: list[str]
