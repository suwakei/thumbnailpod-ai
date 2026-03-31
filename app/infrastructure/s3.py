import logging
from io import BytesIO

import aioboto3
import httpx
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Client:
    def __init__(self) -> None:
        self._session = aioboto3.Session()

    async def upload_from_url(self, url: str, key: str) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=30)
            resp.raise_for_status()
        return await self.upload_bytes(data=resp.content, key=key, content_type="image/png")

    async def upload_image(self, image: Image.Image, key: str) -> str:
        buf = BytesIO()
        image.save(buf, format="PNG")
        return await self.upload_bytes(data=buf.getvalue(), key=key, content_type="image/png")

    async def upload_bytes(self, data: bytes, key: str, content_type: str) -> str:
        async with self._session.client("s3", region_name=settings.aws_region) as s3:
            await s3.put_object(
                Bucket=settings.s3_bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        logger.debug("Uploaded s3://%s/%s", settings.s3_bucket, key)
        return key

    async def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        async with self._session.client("s3", region_name=settings.aws_region) as s3:
            return await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.s3_bucket, "Key": key},
                ExpiresIn=expires_in,
            )
