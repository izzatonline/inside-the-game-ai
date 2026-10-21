"""LLM access. Azure OpenAI (via a Microsoft Foundry deployment) when configured, else offline.

Every caller must treat a None return as "fall back to templates" so the demo
never dies on a model/network failure.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

log = logging.getLogger("itg.llm")


class OfflineLLM:
    name = "offline"
    available = False

    def complete(self, system: str, user: str, max_tokens: int = 250) -> Optional[str]:
        return None


class AzureLLM:
    name = "azure-openai"
    available = True

    def __init__(self) -> None:
        from openai import AzureOpenAI  # lazy: optional dependency

        endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        self.deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
        version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
        key = os.environ.get("AZURE_OPENAI_API_KEY")
        if key:
            self.client = AzureOpenAI(azure_endpoint=endpoint, api_key=key, api_version=version)
        else:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider

            provider = get_bearer_token_provider(
                DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
            self.client = AzureOpenAI(azure_endpoint=endpoint, azure_ad_token_provider=provider,
                                      api_version=version)

    def complete(self, system: str, user: str, max_tokens: int = 250) -> Optional[str]:
        reasoning = self.deployment.lower().startswith(("gpt-5", "gpt-6", "o1", "o3", "o4"))
        # reasoning models reject max_tokens/temperature and spend part of the budget "thinking"
        extra = ({"max_completion_tokens": max_tokens + 400, "reasoning_effort": "minimal"} if reasoning
                 else {"max_tokens": max_tokens, "temperature": 0.4})
        try:
            r = self.client.chat.completions.create(
                model=self.deployment,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                timeout=20, **extra)
            return (r.choices[0].message.content or "").strip() or None
        except Exception as exc:  # noqa: BLE001 - degrade, never crash the stream
            log.warning("LLM call failed, using template fallback: %s", exc)
            return None


def get_llm():
    if os.environ.get("FOUNDRY_PROJECT_ENDPOINT") and os.environ.get("FOUNDRY_MODEL"):
        try:
            from .maf import FoundryLLM

            return FoundryLLM()
        except Exception as exc:  # noqa: BLE001 - e.g. Python <3.10 or agent-framework missing
            log.warning("Foundry unavailable (%s); trying Azure OpenAI / offline", exc)
    if os.environ.get("AZURE_OPENAI_ENDPOINT") and os.environ.get("AZURE_OPENAI_DEPLOYMENT"):
        try:
            return AzureLLM()
        except Exception as exc:  # noqa: BLE001
            log.warning("Azure LLM unavailable (%s); running offline", exc)
    return OfflineLLM()
