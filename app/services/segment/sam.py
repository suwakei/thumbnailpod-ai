import logging
from io import BytesIO

import numpy as np
from fastapi import HTTPException
from PIL import Image

from app.core.config import settings
from app.core.security import fetch_remote_image_bytes
from app.infrastructure.s3 import S3Client
from app.schemas.segment import Layer, SegmentRequest, SegmentResponse

logger = logging.getLogger(__name__)

_LABELS = ["background", "person", "text_region"]


class SegmentService:
    """Segment Anything Model (SAM) for layer separation (Phase 2)."""

    def __init__(self) -> None:
        self._s3 = S3Client()
        self._predictor = None

    def _load_sam(self):
        from segment_anything import SamAutomaticMaskGenerator, sam_model_registry  # noqa: PLC0415

        if self._predictor is None:
            sam = sam_model_registry["vit_h"](checkpoint=settings.sam_model_checkpoint)
            sam.to("cuda")
            self._predictor = SamAutomaticMaskGenerator(sam)
        return self._predictor

    async def segment(self, req: SegmentRequest) -> SegmentResponse:
        logger.info("SAM segment start job_id=%s", req.job_id)

        try:
            image_bytes = await fetch_remote_image_bytes(str(req.image_url), timeout=15.0)
        except Exception as e:
            logger.error("Image download failed job_id=%s: %s", req.job_id, e)
            raise HTTPException(status_code=500, detail="Image download failed")

        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        image_np = np.array(image)

        import asyncio  # noqa: PLC0415

        loop = asyncio.get_event_loop()
        try:
            masks = await loop.run_in_executor(None, self._run_sam, image_np)
        except Exception as e:
            logger.error("SAM segmentation failed job_id=%s: %s", req.job_id, e)
            raise HTTPException(status_code=500, detail="Segmentation failed")

        try:
            layers = await self._upload_layers(masks, image, req)
        except Exception as e:
            logger.error("S3 upload failed job_id=%s: %s", req.job_id, e)
            raise HTTPException(status_code=500, detail="Storage upload failed")

        logger.info("SAM segment done job_id=%s layers=%d", req.job_id, len(layers))
        return SegmentResponse(job_id=req.job_id, layers=layers)

    def _run_sam(self, image_np: np.ndarray) -> list[dict]:
        predictor = self._load_sam()
        return predictor.generate(image_np)

    async def _upload_layers(
        self,
        masks: list[dict],
        original: Image.Image,
        req: SegmentRequest,
    ) -> list[Layer]:
        layers = []
        for i, mask_data in enumerate(masks[: len(_LABELS)]):
            label = _LABELS[i] if i < len(_LABELS) else f"layer_{i}"
            mask = Image.fromarray(mask_data["segmentation"].astype(np.uint8) * 255)
            rgba = original.copy().convert("RGBA")
            rgba.putalpha(mask)
            buf = BytesIO()
            rgba.save(buf, format="PNG")
            buf.seek(0)
            s3_key = f"layers/{req.job_id}/{label}.png"
            await self._s3.upload_bytes(data=buf.read(), key=s3_key, content_type="image/png")
            layers.append(Layer(label=label, s3_key=s3_key))
        return layers
