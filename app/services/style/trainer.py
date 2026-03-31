import json
import logging
import uuid

from app.infrastructure.sqs import SQSClient
from app.schemas.style import StyleTrainRequest, StyleTrainResponse

logger = logging.getLogger(__name__)


class StyleTrainer:
    """Enqueues LoRA / style-ref training jobs to SQS.

    Heavy training is executed by the AI Worker (separate ECS Task).
    """

    def __init__(self) -> None:
        self._sqs = SQSClient()

    async def enqueue(self, req: StyleTrainRequest) -> StyleTrainResponse:
        job_id = str(uuid.uuid4())
        message = {
            "task": "style_train",
            "job_id": job_id,
            "style_model_id": str(req.style_model_id),
            "user_id": str(req.user_id),
            "image_urls": [str(u) for u in req.image_urls],
            "phase": req.phase,
        }
        await self._sqs.send_message(json.dumps(message))
        logger.info("Style train enqueued job_id=%s phase=%s", job_id, req.phase)
        return StyleTrainResponse(
            style_model_id=req.style_model_id,
            job_id=job_id,
            phase=req.phase,
        )
