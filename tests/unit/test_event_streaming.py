"""Unit tests for Phase 2 event streaming (publisher, consumer, DLQ)."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

from redis.exceptions import ResponseError
from tracenova_api.event_consumer import EventConsumer
from tracenova_api.event_publisher import EventPublisher
from tracenova_common.events import EventType, PipelineEvent


def test_event_publisher_publishes_to_redis() -> None:
    """Publisher calls xadd with serialized JSON event."""
    async def _test() -> None:
        mock_redis = AsyncMock()
        publisher = EventPublisher(mock_redis, "tracenova:events")

        event = PipelineEvent(
            event_id=uuid4(),
            event_type=EventType.PIPELINE_STARTED,
            schema_version=1,
            pipeline_id=uuid4(),
            correlation_id=uuid4(),
            timestamp=datetime.now(UTC),
            payload={"attempt": 1},
        )

        await publisher.publish(event)

        mock_redis.xadd.assert_called_once()
        args, kwargs = mock_redis.xadd.call_args
        assert args[0] == "tracenova:events"
        assert "event" in args[1]

    asyncio.run(_test())


def test_event_consumer_processes_batch() -> None:
    """Consumer reads stream batch, invokes handler, and acknowledges message."""
    async def _test() -> None:
        mock_redis = AsyncMock()
        mock_redis.xgroup_create.side_effect = ResponseError(
            "BUSYGROUP Consumer Group name already exists"
        )

        event = PipelineEvent(
            event_id=uuid4(),
            event_type=EventType.PIPELINE_COMPLETED,
            schema_version=1,
            pipeline_id=uuid4(),
            correlation_id=uuid4(),
            timestamp=datetime.now(UTC),
            payload={"duration_ms": 1000},
        )

        mock_redis.xreadgroup.return_value = [
            ("tracenova:events", [("1700000000000-0", {"event": event.model_dump_json()})])
        ]

        consumer = EventConsumer(
            redis_client=mock_redis,
            stream_name="tracenova:events",
            group_name="tracenova-processors",
            consumer_name="worker-1",
        )

        processed_events: list[PipelineEvent] = []

        async def sample_handler(evt: PipelineEvent) -> None:
            processed_events.append(evt)

        count = await consumer.consume_batch(sample_handler)

        assert count == 1
        assert len(processed_events) == 1
        assert processed_events[0].event_type == EventType.PIPELINE_COMPLETED
        mock_redis.xack.assert_called_once_with(
            "tracenova:events",
            "tracenova-processors",
            "1700000000000-0",
        )

    asyncio.run(_test())


def test_event_consumer_routes_malformed_event_to_dlq() -> None:
    """Consumer catches malformed message, sends to DLQ, and acknowledges original."""
    async def _test() -> None:
        mock_redis = AsyncMock()
        mock_redis.xgroup_create.return_value = None
        mock_redis.xreadgroup.return_value = [
            ("tracenova:events", [("1700000000000-1", {"invalid_key": "bad_data"})])
        ]

        consumer = EventConsumer(
            redis_client=mock_redis,
            stream_name="tracenova:events",
            group_name="tracenova-processors",
            consumer_name="worker-1",
            dlq_stream_name="tracenova:events:dlq",
        )

        handler = AsyncMock()
        count = await consumer.consume_batch(handler)

        assert count == 1
        handler.assert_not_called()
        mock_redis.xadd.assert_called_once()
        dlq_stream = mock_redis.xadd.call_args[0][0]
        assert dlq_stream == "tracenova:events:dlq"
        mock_redis.xack.assert_called_once_with(
            "tracenova:events",
            "tracenova-processors",
            "1700000000000-1",
        )

    asyncio.run(_test())
