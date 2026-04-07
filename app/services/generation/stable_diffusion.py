import logging

from fastapi import HTTPException

from app.core.config import settings
from app.infrastructure.s3 import S3Client
from app.schemas.generate import GenerateRequest, GenerateResponse

logger = logging.getLogger(__name__)


class StableDiffusionService:
    """Stable Diffusion XL inference (Phase 2).

    Heavy generation (LoRA, controlnet) is offloaded to the AI Worker via SQS.
    This class handles lightweight SDXL inference directly on the AI Service container.
    """

    def __init__(self) -> None:
        self._s3 = S3Client()
        self._pipe = None  # Lazy-loaded to avoid GPU memory on startup

    def _load_pipeline(self):
        # Import deferred so the service starts without a GPU
        import torch  # noqa: PLC0415
        from diffusers import StableDiffusionXLPipeline  # noqa: PLC0415

        if self._pipe is None:
            self._pipe = StableDiffusionXLPipeline.from_pretrained(
                settings.sd_model_id,
                torch_dtype=torch.float16,
                use_safetensors=True,
            ).to("cuda")
        return self._pipe

    async def generate(self, req: GenerateRequest) -> GenerateResponse:
        logger.info("SDXL generation start job_id=%s", req.job_id)

        import asyncio  # noqa: PLC0415

        loop = asyncio.get_event_loop()
        try:
            image = await loop.run_in_executor(None, self._run_inference, req)
        except Exception as e:
            logger.error("SDXL inference failed job_id=%s: %s", req.job_id, e)
            raise HTTPException(status_code=500, detail="Image generation failed")

        try:
            s3_key = await self._s3.upload_image(
                image=image,
                key=f"thumbnails/{req.user_id}/{req.job_id}.png",
            )
        except Exception as e:
            logger.error("S3 upload failed job_id=%s: %s", req.job_id, e)
            raise HTTPException(status_code=500, detail="Storage upload failed")

        logger.info("SDXL generation done job_id=%s s3_key=%s", req.job_id, s3_key)
        return GenerateResponse(
            job_id=req.job_id,
            s3_key=s3_key,
            width=req.width,
            height=req.height,
        )

    def load_lora(self, adapter_dir: str) -> None:
        """Load LoRA adapter weights into the pipeline."""
        pipe = self._load_pipeline()
        pipe.load_lora_weights(adapter_dir)
        logger.info("LoRA adapter loaded from %s", adapter_dir)

    def unload_lora(self) -> None:
        """Unload LoRA adapter weights from the pipeline."""
        if self._pipe is not None:
            self._pipe.unload_lora_weights()
            logger.info("LoRA adapter unloaded")

    def _run_inference(self, req: GenerateRequest):
        pipe = self._load_pipeline()
        result = pipe(
            prompt=req.prompt,
            negative_prompt=req.negative_prompt or "",
            width=req.width,
            height=req.height,
            num_inference_steps=30,
        )
        return result.images[0]
