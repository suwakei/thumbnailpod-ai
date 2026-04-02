from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.internal import edit, generate, jobs, psd, segment, style
from app.core.config import settings
from app.core.logging import setup_logging


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
