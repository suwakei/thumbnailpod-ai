import logging

import aioboto3

from app.core.config import settings

logger = logging.getLogger(__name__)


class SQSClient:
    def __init__(self) -> None:
        self._session = aioboto3.Session()

    async def send_message(self, body: str, delay_seconds: int = 0) -> str:
        async with self._session.client("sqs", region_name=settings.aws_region) as sqs:
            response = await sqs.send_message(
                QueueUrl=settings.sqs_queue_url,
                MessageBody=body,
                DelaySeconds=delay_seconds,
            )
        message_id = response["MessageId"]
        logger.debug("SQS message sent id=%s", message_id)
        return message_id
