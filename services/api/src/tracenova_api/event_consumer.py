"""Redis Stream consumer for pipeline events."""

from collections.abc import Awaitable, Callable

from redis.asyncio import Redis
from redis.exceptions import ResponseError
from tracenova_common.events import PipelineEvent

EventHandler = Callable[[PipelineEvent], Awaitable[None]]


class EventConsumer:
    """Reads and acknowledges pipeline events through a Redis consumer group."""

    def __init__(
        self,
        redis_client: Redis,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        dlq_stream_name: str = "tracenova:events:dlq",
    ) -> None:
        self._redis_client = redis_client
        self._stream_name = stream_name
        self._group_name = group_name
        self._consumer_name = consumer_name
        self._dlq_stream_name = dlq_stream_name

    async def ensure_group(self) -> None:
        """Create the consumer group once."""
        try:
            await self._redis_client.xgroup_create(
                name=self._stream_name,
                groupname=self._group_name,
                id="0",
                mkstream=True,
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def consume_batch(
        self,
        handler: EventHandler,
        count: int = 10,
    ) -> int:
        """Process and acknowledge available events, sending malformed ones to DLQ."""
        await self.ensure_group()

        messages = await self._redis_client.xreadgroup(
            groupname=self._group_name,
            consumername=self._consumer_name,
            streams={self._stream_name: ">"},
            count=count,
            block=1_000,
        )

        processed_count = 0

        for _, stream_messages in messages:
            for message_id, fields in stream_messages:
                try:
                    raw_event = fields.get("event")
                    if raw_event is None:
                        raise ValueError("Redis Stream message has no event field.")

                    event = PipelineEvent.model_validate_json(raw_event)
                    await handler(event)
                except Exception as error:
                    # Publish corrupted or failing message to DLQ
                    await self._redis_client.xadd(
                        self._dlq_stream_name,
                        {
                            "original_message_id": message_id,
                            "error": str(error),
                            "raw_fields": str(fields),
                        },
                    )
                finally:
                    await self._redis_client.xack(
                        self._stream_name,
                        self._group_name,
                        message_id,
                    )
                    processed_count += 1

        return processed_count