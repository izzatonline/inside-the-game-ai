"""Event-driven ingest. Match events flow through a bus, so the producer (feed / generator)
and the insight engine are decoupled and can scale independently.

* in-memory (default): generator task -> Broadcaster
* Azure Event Hubs (ITG_INGEST=eventhubs): `python -m itg.publisher` sends; the server consumes.
  Auth is Entra ID (DefaultAzureCredential / managed identity); no connection strings.

Late joiners get the match history replayed silently (state only), then live events.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import AsyncIterator, List, Set

from .generator import DEFAULT_MATCH, generate_match
from .models import Event


async def generator_source(seed: int = 7, speed: float = 60.0, match: str = DEFAULT_MATCH) -> AsyncIterator[Event]:
    prev = 0.0
    for ev in generate_match(seed, match=match):
        await asyncio.sleep(max(0.0, min(ev.t - prev, 60)) / max(speed, 1))
        prev = ev.t
        yield ev


async def eventhubs_source() -> AsyncIterator[Event]:
    from azure.eventhub.aio import EventHubConsumerClient
    from azure.identity.aio import DefaultAzureCredential

    q: asyncio.Queue = asyncio.Queue()

    async def on_event(ctx, data):
        if data is not None:
            await q.put(Event.from_dict(json.loads(data.body_as_str())))

    client = EventHubConsumerClient(
        fully_qualified_namespace=os.environ["EVENTHUB_NAMESPACE"],  # <ns>.servicebus.windows.net
        eventhub_name=os.environ["EVENTHUB_NAME"],
        consumer_group=os.environ.get("EVENTHUB_CONSUMER_GROUP", "$Default"),
        credential=DefaultAzureCredential())
    task = asyncio.create_task(client.receive(on_event=on_event, starting_position="@latest"))
    try:
        while True:
            yield await q.get()
    finally:
        task.cancel()
        await client.close()


class Broadcaster:
    """Fans one ingest stream out to many viewers; keeps history for late joiners."""

    def __init__(self, source: AsyncIterator[Event]) -> None:
        self.source = source
        self.history: List[Event] = []
        self.subscribers: Set[asyncio.Queue] = set()
        self.done = False
        self.task: asyncio.Task = asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        try:
            async for ev in self.source:
                self.history.append(ev)
                for q in list(self.subscribers):
                    q.put_nowait(ev)
        finally:
            self.done = True
            for q in list(self.subscribers):
                q.put_nowait(None)

    def subscribe(self):
        """Returns (history snapshot, live queue). No await between the two: no gaps/dupes."""
        q: asyncio.Queue = asyncio.Queue()
        if self.done:
            q.put_nowait(None)
        self.subscribers.add(q)
        return list(self.history), q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.subscribers.discard(q)


def make_source(seed: int, speed: float, match: str = DEFAULT_MATCH) -> AsyncIterator[Event]:
    if os.environ.get("ITG_INGEST") == "eventhubs":
        return eventhubs_source()
    return generator_source(seed, speed, match)
