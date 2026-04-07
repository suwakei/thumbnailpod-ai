"""Thumbnail layer editor service.

Applies text_change, color_adjust, and move operations to individual layers,
then recomposites the final image.
"""

import asyncio
import logging
from io import BytesIO

import httpx
from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from app.infrastructure.s3 import S3Client
from app.schemas.edit import EditOperation, EditOperationType, EditRequest, EditResponse

logger = logging.getLogger(__name__)


class EditService:
    def __init__(self) -> None:
        self._s3 = S3Client()

    async def edit(self, req: EditRequest) -> EditResponse:
        logger.info("Edit start job_id=%s ops=%d", req.job_id, len(req.operations))

        # Determine which layers are affected
        affected_labels = {op.layer for op in req.operations}
        unchanged = [label for label in req.original_layers if label not in affected_labels]

        # Download affected layers
        layer_images: dict[str, Image.Image] = {}
        for label in affected_labels:
            if label not in req.original_layers:
                continue
            s3_key = req.original_layers[label]
            try:
                layer_images[label] = await self._download_layer(s3_key)
            except httpx.HTTPError as e:
                logger.error("Layer download failed job_id=%s label=%s: %s", req.job_id, label, e)
                raise HTTPException(status_code=500, detail="Image download failed")

        # Apply operations
        loop = asyncio.get_event_loop()
        for op in req.operations:
            if op.layer not in layer_images:
                continue
            img = layer_images[op.layer]
            try:
                layer_images[op.layer] = await loop.run_in_executor(
                    None, self._apply_operation, img, op
                )
            except Exception as e:
                logger.error("Edit operation failed job_id=%s op=%s: %s", req.job_id, op.type, e)
                raise HTTPException(status_code=500, detail="Edit operation failed")

        # Recomposite
        composite = await self._recomposite(req, layer_images, unchanged)

        # Upload updated layers + composite
        updated_layers: dict[str, str] = {}
        try:
            for label, img in layer_images.items():
                s3_key = f"edited/{req.job_id}/{label}.png"
                await self._upload_image(img, s3_key)
                updated_layers[label] = s3_key

            # Upload composite
            composite_key = f"edited/{req.job_id}/composite.png"
            await self._upload_image(composite, composite_key)
            updated_layers["composite"] = composite_key
        except Exception as e:
            logger.error("S3 upload failed job_id=%s: %s", req.job_id, e)
            raise HTTPException(status_code=500, detail="Storage upload failed")

        logger.info("Edit done job_id=%s updated=%d", req.job_id, len(updated_layers))
        return EditResponse(
            job_id=req.job_id,
            layers=updated_layers,
            unchanged_layers=unchanged,
        )

    def _apply_operation(self, img: Image.Image, op: EditOperation) -> Image.Image:
        if op.type == EditOperationType.TEXT_CHANGE:
            return self._apply_text_change(img, op)
        elif op.type == EditOperationType.COLOR_ADJUST:
            return self._apply_color_adjust(img, op)
        elif op.type == EditOperationType.MOVE:
            return self._apply_move(img, op)
        return img

    def _apply_text_change(self, img: Image.Image, op: EditOperation) -> Image.Image:
        if not op.content:
            return img
        result = img.copy().convert("RGBA")
        draw = ImageDraw.Draw(result)
        x = op.position.x if op.position else 10
        y = op.position.y if op.position else 10
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        except (OSError, IOError):
            font = ImageFont.load_default()
        draw.text((x, y), op.content, fill=(255, 255, 255, 255), font=font)
        return result

    def _apply_color_adjust(self, img: Image.Image, op: EditOperation) -> Image.Image:
        result = img.copy()
        if op.brightness is not None:
            result = ImageEnhance.Brightness(result).enhance(op.brightness)
        if op.contrast is not None:
            result = ImageEnhance.Contrast(result).enhance(op.contrast)
        if op.saturation is not None:
            result = ImageEnhance.Color(result).enhance(op.saturation)
        return result

    def _apply_move(self, img: Image.Image, op: EditOperation) -> Image.Image:
        if not op.position:
            return img
        canvas = Image.new("RGBA", img.size, (0, 0, 0, 0))
        canvas.paste(img, (op.position.x, op.position.y))
        return canvas

    async def _recomposite(
        self,
        req: EditRequest,
        updated: dict[str, Image.Image],
        unchanged_labels: list[str],
    ) -> Image.Image:
        # Start with background or first available layer
        all_images: dict[str, Image.Image] = dict(updated)

        # Download unchanged layers for compositing
        for label in unchanged_labels:
            if label in req.original_layers and label != "composite":
                all_images[label] = await self._download_layer(req.original_layers[label])

        # Layer ordering
        order = ["background_layer", "person_layer", "text_layer", "effect_layer"]
        first = True
        composite: Image.Image | None = None

        for label in order:
            if label in all_images:
                if first:
                    composite = all_images[label].copy().convert("RGBA")
                    first = False
                else:
                    layer = all_images[label].convert("RGBA")
                    composite = Image.alpha_composite(composite, layer)

        # Add any remaining layers not in the standard order
        for label, img in all_images.items():
            if label not in order and label != "composite":
                layer = img.convert("RGBA")
                if composite is None:
                    composite = layer
                else:
                    composite = Image.alpha_composite(composite, layer)

        if composite is None:
            composite = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))

        return composite

    async def _download_layer(self, s3_key: str) -> Image.Image:
        url = await self._s3.generate_presigned_url(s3_key)
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=15)
            resp.raise_for_status()
        return Image.open(BytesIO(resp.content)).convert("RGBA")

    async def _upload_image(self, img: Image.Image, s3_key: str) -> None:
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        await self._s3.upload_bytes(data=buf.read(), key=s3_key, content_type="image/png")
