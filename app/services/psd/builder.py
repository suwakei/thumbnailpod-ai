"""PSD file generation using psd-tools (Phase 2).

Builds a layered PSD from SAM segmentation results so creators can
edit the thumbnail in Photoshop / Affinity Photo.
"""

import logging
from io import BytesIO
from uuid import UUID

import httpx
from fastapi import HTTPException
from PIL import Image

from app.infrastructure.s3 import S3Client

logger = logging.getLogger(__name__)


class PSDBuilder:
    def __init__(self) -> None:
        self._s3 = S3Client()

    async def build_from_layers(
        self,
        job_id: UUID,
        user_id: UUID,
        layer_s3_keys: list[tuple[str, str]],  # [(label, s3_key), ...]
        base_image_url: str,
    ) -> str:
        """Download layer PNGs, compose a PSD, upload to S3, return s3_key."""
        logger.info("PSD build start job_id=%s layers=%d", job_id, len(layer_s3_keys))

        try:
            base_image = await self._fetch_image(base_image_url)
            layer_images = await self._fetch_layer_images(layer_s3_keys)
        except httpx.HTTPError as e:
            logger.error("Image download failed job_id=%s: %s", job_id, e)
            raise HTTPException(status_code=500, detail="Image download failed")

        try:
            psd_bytes = await self._compose_psd(base_image, layer_images)
        except Exception as e:
            logger.error("PSD composition failed job_id=%s: %s", job_id, e)
            raise HTTPException(status_code=500, detail="PSD build failed")

        s3_key = f"thumbnails/{user_id}/{job_id}.psd"
        try:
            await self._s3.upload_bytes(
                data=psd_bytes, key=s3_key, content_type="image/vnd.adobe.photoshop"
            )
        except Exception as e:
            logger.error("S3 upload failed job_id=%s: %s", job_id, e)
            raise HTTPException(status_code=500, detail="Storage upload failed")

        logger.info("PSD upload done job_id=%s s3_key=%s", job_id, s3_key)
        return s3_key

    async def _fetch_image(self, url: str) -> Image.Image:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=15)
            resp.raise_for_status()
        return Image.open(BytesIO(resp.content)).convert("RGBA")

    async def _fetch_layer_images(
        self, layer_s3_keys: list[tuple[str, str]]
    ) -> list[tuple[str, Image.Image]]:
        layers = []
        for label, key in layer_s3_keys:
            url = await self._s3.generate_presigned_url(key)
            img = await self._fetch_image(url)
            layers.append((label, img))
        return layers

    async def _compose_psd(
        self,
        base: Image.Image,
        layers: list[tuple[str, Image.Image]],
    ) -> bytes:
        import asyncio  # noqa: PLC0415

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._build_psd_sync, base, layers)

    def _build_psd_sync(
        self,
        base: Image.Image,
        layers: list[tuple[str, Image.Image]],
    ) -> bytes:
        from psd_tools import PSDImage  # noqa: PLC0415
        from psd_tools.constants import ColorMode  # noqa: PLC0415

        width, height = base.size
        psd = PSDImage.new(ColorMode.RGB, (width, height))

        # Add base layer
        base_layer = psd.compose()
        if base_layer:
            base_layer.name = "Background"

        # Add each segmented layer
        for label, img in reversed(layers):
            pixel_layer = psd._record  # low-level access
            # psd-tools public API: use frompil
            from psd_tools.api.psd_image import PixelLayer  # noqa: PLC0415

            layer = PixelLayer.frompil(img, psd)
            layer.name = label
            psd.append(layer)

        buf = BytesIO()
        psd.save(buf)
        return buf.getvalue()
