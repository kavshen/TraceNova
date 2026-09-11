import structlog
from redis.asyncio import Redis
from tracenova_common.events import PipelineEvent

logger = structlog.get_logger()


class EventPublisher:
    """Publishes versioned pipeline events to a Redis Stream."""

    def __init__(self, redis_client: Redis, stream_name: str) -> None:
        self._redis_client = redis_client
        self._stream_name = stream_name

    async def publish(self, event: PipelineEvent) -> None:
        """Append one event to the configured Redis Stream."""
        try:
            await self._redis_client.xadd(
                self._stream_name,
                {"event": event.model_dump_json()},
            )
        except Exception as error:
            logger.warning(
                "event_publishing_failed",
                event_id=str(event.event_id),
                error=str(error),
            )