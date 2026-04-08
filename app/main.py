import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

from app.api.internal import edit, generate, jobs, psd, segment, style
from app.core.config import settings
from app.core.logging import setup_logging
from app.schemas.health import (
    GpuInfo,
    HealthDetailResponse,
    ServiceHealth,
    SystemInfo,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


app = FastAPI(
    title="ThumbnailAI - AI Service",
    version="1.0.0",
    # Internal service: disable public docs in production
    docs_url="/docs" if settings.env != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.include_router(generate.router, prefix="/internal")
app.include_router(style.router, prefix="/internal/style")
app.include_router(jobs.router, prefix="/internal")
app.include_router(segment.router, prefix="/internal")
app.include_router(psd.router, prefix="/internal")
app.include_router(edit.router, prefix="/internal")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


async def _check_database() -> ServiceHealth:
    """Check database connectivity by running a simple query."""
    try:
        from app.infrastructure.database import get_pool  # noqa: PLC0415

        start = time.monotonic()
        pool = await get_pool()
        await pool.fetchval("SELECT 1")
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return ServiceHealth(status="ok", latency_ms=latency_ms)
    except Exception as e:
        logger.warning("Health check: database unavailable: %s", e)
        return ServiceHealth(status="error")


async def _check_s3() -> ServiceHealth:
    """Check S3 reachability by performing a head_bucket call."""
    try:
        import aioboto3  # noqa: PLC0415

        session = aioboto3.Session()
        async with session.client("s3", region_name=settings.aws_region) as s3:
            await s3.head_bucket(Bucket=settings.s3_bucket)
        return ServiceHealth(status="ok")
    except Exception as e:
        logger.warning("Health check: S3 unavailable: %s", e)
        return ServiceHealth(status="error")


def _check_gpu() -> GpuInfo:
    """Check GPU availability using torch (lazy import)."""
    try:
        import torch  # noqa: PLC0415

        if not torch.cuda.is_available():
            return GpuInfo(available=False)

        device_name = torch.cuda.get_device_name(0)
        mem_total = torch.cuda.get_device_properties(0).total_mem
        mem_used = torch.cuda.memory_allocated(0)
        return GpuInfo(
            available=True,
            device_name=device_name,
            memory_total_gb=round(mem_total / (1024**3), 2),
            memory_used_gb=round(mem_used / (1024**3), 2),
        )
    except Exception:
        return GpuInfo(available=False)


def _check_system() -> SystemInfo:
    """Gather system info using psutil if available."""
    python_version = sys.version.split()[0]
    try:
        import psutil  # noqa: PLC0415

        return SystemInfo(
            python_version=python_version,
            cpu_percent=psutil.cpu_percent(interval=0.1),
            memory_percent=psutil.virtual_memory().percent,
        )
    except Exception:
        return SystemInfo(python_version=python_version)


@app.get("/health/detail", response_model=HealthDetailResponse)
async def health_detail() -> HealthDetailResponse:
    db_health = await _check_database()
    s3_health = await _check_s3()
    gpu_info = _check_gpu()
    system_info = _check_system()

    services = {
        "database": db_health,
        "s3": s3_health,
    }

    overall = "ok" if all(s.status == "ok" for s in services.values()) else "degraded"

    return HealthDetailResponse(
        status=overall,
        version=app.version,
        services=services,
        gpu=gpu_info,
        system=system_info,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )
