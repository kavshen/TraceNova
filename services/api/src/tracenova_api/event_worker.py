"""Background worker that consumes TraceNova pipeline events."""

import asyncio
import socket

import structlog
from redis.asyncio import Redis
from tracenova_common.events import PipelineEvent
from tracenova_config.settings import get_settings
from tracenova_logging.logging import configure_logging

from tracenova_api.event_consumer import EventConsumer

logger = structlog.get_logger()


async def handle_event(event: PipelineEvent) -> None:
    """Process one event before it is acknowledged."""
    logger.info(
        "pipeline_event_processed",
        event_id=str(event.event_id),
        event_type=event.event_type,
        pipeline_id=str(event.pipeline_id),
        correlation_id=str(event.correlation_id),
    )


async def run_worker() -> None:
    """Continuously consume pipeline events."""
    settings = get_settings()
    configure_logging(settings.log_level)

    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    consumer = EventConsumer(
        redis_client=redis_client,
        stream_name=settings.redis_stream_name,
        group_name=settings.redis_consumer_group,
        consumer_name=f"event-worker-{socket.gethostname()}",
    )

    try:
        while True:
            await consumer.consume_batch(handle_event)
    finally:
        await redis_client.aclose()


def main() -> None:
    """Start the worker process."""
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()