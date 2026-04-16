import logging

import numpy as np
from PIL import Image

from app.core.security import fetch_remote_image_bytes
from app.schemas.style import StyleAnalyzeRequest, StyleAnalyzeResponse, StyleMetadata

logger = logging.getLogger(__name__)

# Dominant color count extracted per image
_N_COLORS = 5


class StyleAnalyzer:
    """Phase 1: Extract color palette and composition features using CLIP.

    No GPU required - runs on CPU for immediate processing.
    """

    def __init__(self) -> None:
        self._clip_model = None
        self._clip_processor = None

    def _load_clip(self):
        from transformers import CLIPModel, CLIPProcessor  # noqa: PLC0415

        from app.core.config import settings  # noqa: PLC0415

        if self._clip_model is None:
            self._clip_processor = CLIPProcessor.from_pretrained(settings.clip_model_id)
            self._clip_model = CLIPModel.from_pretrained(settings.clip_model_id)
        return self._clip_model, self._clip_processor

    async def analyze(self, req: StyleAnalyzeRequest) -> StyleAnalyzeResponse:
        logger.info("Style analysis start user_id=%s images=%d", req.user_id, len(req.image_urls))

        images = await self._fetch_images(req.image_urls)

        color_palette = self._extract_color_palette(images)
        composition = self._extract_composition(images)
        embedding = self._extract_clip_embedding(images)

        metadata = StyleMetadata(
            color_palette=color_palette,
            composition_features=composition,
            clip_embedding=embedding,
        )
        logger.info("Style analysis done user_id=%s", req.user_id)
        return StyleAnalyzeResponse(style_metadata=metadata)

    async def _fetch_images(self, urls: list) -> list[Image.Image]:
        from io import BytesIO  # noqa: PLC0415

        images = []
        for url in urls:
            data = await fetch_remote_image_bytes(str(url), timeout=10.0)
            images.append(Image.open(BytesIO(data)).convert("RGB"))
        return images

    def _extract_color_palette(self, images: list[Image.Image]) -> list[str]:
        all_pixels = []
        for img in images:
            small = img.resize((50, 50))
            all_pixels.extend(np.array(small).reshape(-1, 3).tolist())

        pixels = np.array(all_pixels, dtype=np.float32)

        # Simple k-means for dominant colors
        from sklearn.cluster import MiniBatchKMeans  # noqa: PLC0415

        kmeans = MiniBatchKMeans(n_clusters=_N_COLORS, n_init=3, random_state=0)
        kmeans.fit(pixels)
        centers = kmeans.cluster_centers_.astype(int)
        return [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in centers]

    def _extract_composition(self, images: list[Image.Image]) -> dict:
        ratios = [img.size[0] / img.size[1] for img in images]
        return {
            "avg_aspect_ratio": float(np.mean(ratios)),
            "image_count": len(images),
        }

    def _extract_clip_embedding(self, images: list[Image.Image]) -> list[float]:
        import torch  # noqa: PLC0415

        model, processor = self._load_clip()
        inputs = processor(images=images, return_tensors="pt", padding=True)
        with torch.no_grad():
            features = model.get_image_features(**inputs)
        mean_embedding = features.mean(dim=0)
        return mean_embedding.tolist()
