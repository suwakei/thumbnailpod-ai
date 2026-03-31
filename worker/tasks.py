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

    # Load LoRA adapter if style_model_id provided (Phase 2)
    if req.style_model_id:
        await _load_lora_adapter(service, req.style_model_id)

    await service.generate(req)


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
    s3 = S3Client()
    lora_key = f"lora-models/{style_model_id}/adapter.safetensors"
    # TODO: download to tmp path and load into pipeline
    logger.info("LoRA adapter load (stub) key=%s", lora_key)


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

    Runs on AI Worker with GPU (2 vCPU / 4 GB, or GPU Spot Instance for Phase 3).
    """
    logger.info("LoRA training start style_model_id=%s", body.get("style_model_id"))
    # TODO: implement DreamBooth / LoRA training pipeline
    # 1. Download images from S3
    # 2. Prepare dataset
    # 3. Run training loop (diffusers + peft)
    # 4. Save adapter weights to S3 under lora-models/{style_model_id}/
    raise NotImplementedError("LoRA training not yet implemented (Phase 2)")
