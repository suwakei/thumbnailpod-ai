"""Concrete task handlers executed by the AI Worker."""

import logging
from uuid import UUID

from app.infrastructure.s3 import S3Client

logger = logging.getLogger(__name__)


async def handle_generate(body: dict) -> None:
    """Heavy SDXL generation with optional LoRA adapter."""
    from app.schemas.generate import GenerateRequest, GenerationEngine  # noqa: PLC0415
    from app.services.generation.stable_diffusion import StableDiffusionService  # noqa: PLC0415

    req = GenerateRequest(
        job_id=body["job_id"],
        user_id=body["user_id"],
        prompt=body["prompt"],
        engine=GenerationEngine.SDXL,
        style_model_id=body.get("style_model_id"),
        negative_prompt=body.get("negative_prompt"),
    )

    service = StableDiffusionService()

    # Load LoRA adapter if style_model_id provided
    if req.style_model_id:
        await _load_lora_adapter(service, req.style_model_id)

    try:
        await service.generate(req)
    finally:
        # Cleanup LoRA weights after generation
        if req.style_model_id:
            service.unload_lora()


async def handle_style_train(body: dict) -> None:
    """LoRA fine-tuning job (Phase 2)."""
    phase = body.get("phase", "style_ref")
    logger.info("Style train phase=%s style_model_id=%s", phase, body.get("style_model_id"))

    if phase == "style_ref":
        await _run_style_ref_training(body)
    elif phase == "lora":
        await _run_lora_training(body)
    else:
        raise ValueError(f"Unknown training phase: {phase}")


async def _load_lora_adapter(service, style_model_id: UUID) -> None:
    """Download LoRA weights from S3 and load into the pipeline."""
    import tempfile  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    s3 = S3Client()
    lora_key = f"lora-models/{style_model_id}/adapter.safetensors"

    # Check local cache first
    cache_dir = Path(tempfile.gettempdir()) / "lora_cache" / str(style_model_id)
    adapter_path = cache_dir / "adapter_model.safetensors"

    if not adapter_path.exists():
        logger.info("LoRA adapter cache miss, downloading key=%s", lora_key)
        cache_dir.mkdir(parents=True, exist_ok=True)
        url = await s3.generate_presigned_url(lora_key)

        import httpx  # noqa: PLC0415

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=60)
            resp.raise_for_status()
        adapter_path.write_bytes(resp.content)
    else:
        logger.info("LoRA adapter cache hit path=%s", adapter_path)

    # Load into pipeline
    service.load_lora(str(cache_dir))


async def _run_style_ref_training(body: dict) -> None:
    """Phase 1: Extract and persist style metadata without GPU training."""
    from pydantic import AnyHttpUrl  # noqa: PLC0415

    from app.schemas.style import StyleAnalyzeRequest  # noqa: PLC0415
    from app.services.style.analyzer import StyleAnalyzer  # noqa: PLC0415

    req = StyleAnalyzeRequest(
        user_id=body["user_id"],
        image_urls=[AnyHttpUrl(u) for u in body["image_urls"]],
    )
    analyzer = StyleAnalyzer()
    result = await analyzer.analyze(req)

    # Persist style_metadata back to DB
    # TODO: update style_models.style_metadata via DB
    logger.info("Style ref training done user_id=%s", body["user_id"])


async def _run_lora_training(body: dict) -> None:
    """Phase 2: LoRA fine-tuning with Diffusers + PEFT.

    Runs on AI Worker with GPU.
    """
    from uuid import UUID as _UUID  # noqa: PLC0415

    from app.services.style.lora_trainer import LoRATrainer  # noqa: PLC0415

    style_model_id = _UUID(body["style_model_id"])
    user_id = _UUID(body["user_id"])
    image_urls = body["image_urls"]

    logger.info(
        "LoRA training start style_model_id=%s images=%d",
        style_model_id,
        len(image_urls),
    )

    trainer = LoRATrainer()
    s3_key = await trainer.train(style_model_id, user_id, image_urls)

    # Update style_model status and s3_key via DB
    from app.infrastructure.database import update_style_model_status  # noqa: PLC0415

    await update_style_model_status(style_model_id, "ready", s3_key=s3_key)
    logger.info("LoRA training complete style_model_id=%s", style_model_id)
