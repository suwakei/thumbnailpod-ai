"""AI Worker - SQS consumer running as a separate ECS Task.

Handles heavy inference: LoRA training, SDXL generation with adapters.
Started independently from the FastAPI service.
"""

import asyncio
import json
import logging
import signal

import aioboto3

from app.core.config import settings
from app.core.logging import setup_logging
from app.infrastructure.database import update_job_status
from app.schemas.job import JobStatus
from worker.tasks import handle_generate, handle_style_train

logger = logging.getLogger(__name__)

_VISIBILITY_TIMEOUT = 900  # 15 minutes (matches SQS config)
_WAIT_TIME = 20  # Long polling


class Worker:
    def __init__(self) -> None:
        self._session = aioboto3.Session()
        self._running = True

    def stop(self, *_) -> None:
        logger.info("Shutdown signal received")
        self._running = False

    async def run(self) -> None:
        logger.info("AI Worker started, polling %s", settings.sqs_queue_url)
        async with self._session.client("sqs", region_name=settings.aws_region) as sqs:
            while self._running:
                response = await sqs.receive_message(
                    QueueUrl=settings.sqs_queue_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=_WAIT_TIME,
                    VisibilityTimeout=_VISIBILITY_TIMEOUT,
                )
                messages = response.get("Messages", [])
                for message in messages:
                    await self._process(sqs, message)

    async def _process(self, sqs, message: dict) -> None:
        receipt = message["ReceiptHandle"]
        body = json.loads(message["Body"])
        job_id = body.get("job_id")
        task = body.get("task")

        logger.info("Processing task=%s job_id=%s", task, job_id)

        try:
            await update_job_status(job_id, JobStatus.PROCESSING)

            if task == "generate":
                await handle_generate(body)
            elif task == "style_train":
                await handle_style_train(body)
            else:
                raise ValueError(f"Unknown task: {task}")

            await update_job_status(job_id, JobStatus.COMPLETED)

            async with self._session.client("sqs", region_name=settings.aws_region) as sqs_del:
                await sqs_del.delete_message(
                    QueueUrl=settings.sqs_queue_url,
                    ReceiptHandle=receipt,
                )
            logger.info("Task done task=%s job_id=%s", task, job_id)

        except Exception as exc:
            logger.exception("Task failed task=%s job_id=%s", task, job_id)
            await update_job_status(job_id, JobStatus.FAILED, error_message=str(exc))
            # Leave message in queue for DLQ handling


async def main() -> None:
    setup_logging()
    worker = Worker()
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
