"""LoRA fine-tuning trainer using DreamBooth + PEFT on SDXL.

Downloads user images from S3, prepares dataset, runs LoRA training,
and uploads adapter weights back to S3.
"""

import asyncio
import logging
import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from uuid import UUID

import httpx
from PIL import Image

from app.core.config import settings
from app.infrastructure.s3 import S3Client

logger = logging.getLogger(__name__)


class LoRATrainer:
    def __init__(self) -> None:
        self._s3 = S3Client()

    async def train(
        self,
        style_model_id: UUID,
        user_id: UUID,
        image_urls: list[str],
    ) -> str:
        """Run LoRA training and return the S3 key of the adapter weights."""
        logger.info(
            "LoRA training start style_model_id=%s images=%d",
            style_model_id,
            len(image_urls),
        )

        work_dir = Path(tempfile.mkdtemp(prefix="lora_"))
        try:
            # 1. Download images
            dataset_dir = work_dir / "dataset"
            dataset_dir.mkdir()
            await self._download_images(image_urls, dataset_dir)

            # 2. Prepare dataset (resize to 1024x1024)
            self._prepare_dataset(dataset_dir)

            # 3. Run training
            output_dir = work_dir / "output"
            output_dir.mkdir()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._run_training, dataset_dir, output_dir)

            # 4. Upload adapter to S3
            adapter_path = output_dir / "adapter_model.safetensors"
            s3_key = f"lora-models/{style_model_id}/adapter.safetensors"
            with open(adapter_path, "rb") as f:
                await self._s3.upload_bytes(
                    data=f.read(),
                    key=s3_key,
                    content_type="application/octet-stream",
                )

            logger.info(
                "LoRA training done style_model_id=%s s3_key=%s",
                style_model_id,
                s3_key,
            )
            return s3_key
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    async def _download_images(self, urls: list[str], dest_dir: Path) -> None:
        async with httpx.AsyncClient() as client:
            for i, url in enumerate(urls):
                try:
                    resp = await client.get(url, timeout=30)
                    resp.raise_for_status()
                    img = Image.open(BytesIO(resp.content)).convert("RGB")
                    img.save(dest_dir / f"image_{i:04d}.png")
                except Exception as e:
                    logger.warning("Failed to download image %d: %s", i, e)

    def _prepare_dataset(self, dataset_dir: Path) -> None:
        """Resize all images to 1024x1024 for SDXL training."""
        for img_path in dataset_dir.glob("*.png"):
            img = Image.open(img_path)
            img = img.resize((1024, 1024), Image.LANCZOS)
            img.save(img_path)

    def _run_training(self, dataset_dir: Path, output_dir: Path) -> None:
        """Synchronous DreamBooth LoRA training with SDXL."""
        import torch  # noqa: PLC0415
        from diffusers import StableDiffusionXLPipeline  # noqa: PLC0415
        from peft import LoraConfig, get_peft_model  # noqa: PLC0415

        logger.info("Loading SDXL base model for LoRA training")
        pipe = StableDiffusionXLPipeline.from_pretrained(
            settings.sd_model_id,
            torch_dtype=torch.float16,
            use_safetensors=True,
        )
        pipe.to("cuda")

        # Configure LoRA
        lora_config = LoraConfig(
            r=4,
            lora_alpha=4,
            target_modules=["to_k", "to_q", "to_v", "to_out.0"],
            lora_dropout=0.0,
        )

        unet = pipe.unet
        unet = get_peft_model(unet, lora_config)
        unet.train()

        # Simple training loop
        optimizer = torch.optim.AdamW(unet.parameters(), lr=1e-4)

        from torchvision import transforms  # noqa: PLC0415

        transform = transforms.Compose(
            [
                transforms.Resize((1024, 1024)),
                transforms.ToTensor(),
                transforms.Normalize([0.5], [0.5]),
            ]
        )

        images = []
        for img_path in sorted(dataset_dir.glob("*.png")):
            img = Image.open(img_path).convert("RGB")
            images.append(transform(img))

        if not images:
            raise ValueError("No training images found")

        dataset = torch.stack(images).to("cuda", dtype=torch.float16)
        num_steps = min(500, max(100, len(images) * 50))

        logger.info("Starting LoRA training: %d steps, %d images", num_steps, len(images))

        for step in range(num_steps):
            idx = step % len(images)
            latent = dataset[idx : idx + 1]

            # Encode to latent space
            with torch.no_grad():
                latents = pipe.vae.encode(latent).latent_dist.sample()
                latents = latents * pipe.vae.config.scaling_factor

            # Add noise
            noise = torch.randn_like(latents)
            timesteps = torch.randint(0, 1000, (1,), device="cuda").long()

            noisy_latents = pipe.scheduler.add_noise(latents, noise, timesteps)

            # Predict noise
            encoder_hidden_states = torch.zeros(
                1,
                77,
                pipe.unet.config.cross_attention_dim,
                device="cuda",
                dtype=torch.float16,
            )
            added_cond_kwargs = {
                "text_embeds": torch.zeros(1, 1280, device="cuda", dtype=torch.float16),
                "time_ids": torch.zeros(1, 6, device="cuda", dtype=torch.float16),
            }

            noise_pred = unet(
                noisy_latents,
                timesteps,
                encoder_hidden_states=encoder_hidden_states,
                added_cond_kwargs=added_cond_kwargs,
            ).sample

            loss = torch.nn.functional.mse_loss(noise_pred, noise)
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()

            if step % 100 == 0:
                logger.info("LoRA step %d/%d loss=%.4f", step, num_steps, loss.item())

        # Save adapter weights
        unet.save_pretrained(str(output_dir))
        logger.info("LoRA adapter saved to %s", output_dir)

        # Cleanup GPU memory
        del pipe, unet, optimizer, dataset
        torch.cuda.empty_cache()
