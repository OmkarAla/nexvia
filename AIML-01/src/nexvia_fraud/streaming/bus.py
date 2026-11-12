"""Transport abstractions so the pipeline can be tested without a broker."""

from __future__ import annotations

from collections import deque
from typing import Protocol

from confluent_kafka import Consumer as _KafkaConsumer
from confluent_kafka import Producer as _KafkaProducer


class Publisher(Protocol):
    def publish(self, topic: str, key: str, value: bytes) -> None: ...


class Consumer(Protocol):
    def poll(self, timeout: float) -> tuple[str, bytes] | None: ...

    def commit(self) -> None: ...


class InMemoryBus:
    def __init__(self) -> None:
        self._messages: deque[tuple[str, bytes]] = deque()

    def publish(self, topic: str, key: str, value: bytes) -> None:
        self._messages.append((topic, value))

    def poll(self, timeout: float) -> tuple[str, bytes] | None:
        if not self._messages:
            return None
        return self._messages.popleft()

    def commit(self) -> None:
        return None


class KafkaPublisher:
    def __init__(self, bootstrap: str) -> None:
        self._producer = _KafkaProducer(
            {
                "bootstrap.servers": bootstrap,
                "enable.idempotence": True,
                "acks": "all",
            }
        )

    def publish(self, topic: str, key: str, value: bytes) -> None:
        self._producer.produce(topic, key=key, value=value)
        self._producer.poll(0)

    def flush(self, timeout: float = 5.0) -> None:
        self._producer.flush(timeout)


class KafkaConsumer:
    def __init__(self, bootstrap: str, group_id: str, topics: list[str]) -> None:
        self._consumer = _KafkaConsumer(
            {
                "bootstrap.servers": bootstrap,
                "group.id": group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )
        self._consumer.subscribe(topics)

    def poll(self, timeout: float) -> tuple[str, bytes] | None:
        message = self._consumer.poll(timeout)
        if message is None or message.error():
            return None
        return message.topic(), message.value()

    def commit(self) -> None:
        self._consumer.commit(asynchronous=False)

    def close(self) -> None:
        self._consumer.close()
