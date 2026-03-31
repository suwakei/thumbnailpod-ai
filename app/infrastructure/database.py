import logging
from uuid import UUID

import asyncpg

from app.core.config import settings
from app.schemas.job import JobStatus, JobStatusResponse

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
    return _pool


async def get_job_status(job_id: UUID) -> JobStatusResponse:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT status, error_message FROM generation_jobs WHERE id = $1",
        job_id,
    )
    if row is None:
        from fastapi import HTTPException  # noqa: PLC0415

        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job_id,
        status=JobStatus(row["status"]),
        error_message=row["error_message"],
    )


async def update_job_status(
    job_id: UUID,
    status: JobStatus,
    error_message: str | None = None,
) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        UPDATE generation_jobs
        SET status = $2, error_message = $3,
            completed_at = CASE WHEN $2 IN ('completed', 'failed') THEN NOW() ELSE NULL END
        WHERE id = $1
        """,
        job_id,
        status.value,
        error_message,
    )
    logger.debug("Job %s status -> %s", job_id, status)
