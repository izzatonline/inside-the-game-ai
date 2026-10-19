"""Publish a synthetic match to Azure Event Hubs at match speed.

    EVENTHUB_NAMESPACE=<ns>.servicebus.windows.net EVENTHUB_NAME=match-events \\
    python -m itg.publisher --seed 7 --speed 60
"""
import argparse
import asyncio
import json
import os

from azure.eventhub import EventData
from azure.eventhub.aio import EventHubProducerClient
from azure.identity.aio import DefaultAzureCredential

from .generator import generate_match


async def main(seed: int, speed: float) -> None:
    producer = EventHubProducerClient(
        fully_qualified_namespace=os.environ["EVENTHUB_NAMESPACE"],
        eventhub_name=os.environ["EVENTHUB_NAME"], credential=DefaultAzureCredential())
    async with producer:
        prev = 0.0
        for ev in generate_match(seed):
            await asyncio.sleep(max(0.0, min(ev.t - prev, 60)) / max(speed, 1))
            prev = ev.t
            batch = await producer.create_batch()
            batch.add(EventData(json.dumps(ev.to_dict())))
            await producer.send_batch(batch)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--speed", type=float, default=60.0)
    a = ap.parse_args()
    asyncio.run(main(a.seed, a.speed))
