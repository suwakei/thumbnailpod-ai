import logging

from fastapi import HTTPException
from openai import AsyncOpenAI

from app.core.config import settings
from app.infrastructure.s3 import S3Client
from app.schemas.generate import GenerateRequest, GenerateResponse

logger = logging.getLogger(__name__)


class DalleService:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._s3 = S3Client()

    async def generate(self, req: GenerateRequest) -> GenerateResponse:
        logger.info("DALL-E 3 generation start job_id=%s", req.job_id)

        try:
            response = await self._client.images.generate(
                model="dall-e-3",
                prompt=req.prompt,
                size=f"{req.width}x{req.height}",
                quality="hd",
                n=1,
            )
        except Exception as e:
            logger.error("DALL-E generation failed job_id=%s: %s", req.job_id, e)
            raise HTTPException(status_code=500, detail="Image generation failed")

        image_url = response.data[0].url
        try:
            s3_key = await self._s3.upload_from_url(
                url=image_url,
                key=f"thumbnails/{req.user_id}/{req.job_id}.png",
            )
        except Exception as e:
            logger.error("S3 upload failed job_id=%s: %s", req.job_id, e)
            raise HTTPException(status_code=500, detail="Storage upload failed")

        logger.info("DALL-E 3 generation done job_id=%s s3_key=%s", req.job_id, s3_key)
        return GenerateResponse(
            job_id=req.job_id,
            s3_key=s3_key,
            width=req.width,
            height=req.height,
        )
