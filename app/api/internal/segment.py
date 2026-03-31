from fastapi import APIRouter, Depends

from app.core.security import verify_internal_secret
from app.schemas.segment import SegmentRequest, SegmentResponse
from app.services.segment.sam import SegmentService

router = APIRouter(dependencies=[Depends(verify_internal_secret)])

_segment = SegmentService()


@router.post("/segment", response_model=SegmentResponse)
async def segment_image(req: SegmentRequest) -> SegmentResponse:
    return await _segment.segment(req)
