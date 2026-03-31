from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.security import verify_internal_secret
from app.infrastructure.database import get_job_status
from app.schemas.job import JobStatusResponse

router = APIRouter(dependencies=[Depends(verify_internal_secret)])


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: UUID) -> JobStatusResponse:
    return await get_job_status(job_id)
