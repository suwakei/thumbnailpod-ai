"""Edit endpoint: apply operations to thumbnail layers and recomposite."""

import logging

from fastapi import APIRouter

from app.schemas.edit import EditRequest, EditResponse
from app.services.edit.editor import EditService

logger = logging.getLogger(__name__)

router = APIRouter()

_editor = EditService()


@router.post("/edit", response_model=EditResponse)
async def edit_thumbnail(req: EditRequest) -> EditResponse:
    logger.info("POST /internal/edit job_id=%s", req.job_id)
    return await _editor.edit(req)
