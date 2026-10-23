"""Azure AI Speech: reads the full-time recap aloud with a neural voice in the viewer's language.

Configured by SPEECH_REGION plus either SPEECH_KEY, or (keyless) SPEECH_RESOURCE_ID with a Microsoft Entra
identity that has the "Cognitive Services Speech User" role on that resource. Without it the app simply
has no "Listen" button.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, Optional
from xml.sax.saxutils import escape

log = logging.getLogger("itg.speech")

VOICES = {"en": ("en-GB", "en-GB-RyanNeural"), "es": ("es-ES", "es-ES-AlvaroNeural"), "ms": ("ms-MY", "ms-MY-OsmanNeural"),
          "fr": ("fr-FR", "fr-FR-HenriNeural"), "ar": ("ar-SA", "ar-SA-HamedNeural"), "pt": ("pt-BR", "pt-BR-AntonioNeural")}
_cache: Dict[str, bytes] = {}


def configured() -> bool:
    return bool(os.environ.get("SPEECH_REGION") and (os.environ.get("SPEECH_KEY") or os.environ.get("SPEECH_RESOURCE_ID")))


def _auth() -> Dict[str, str]:
    key = os.environ.get("SPEECH_KEY")
    if key:
        return {"Ocp-Apim-Subscription-Key": key}
    from azure.identity import DefaultAzureCredential

    token = DefaultAzureCredential().get_token("https://cognitiveservices.azure.com/.default").token
    return {"Authorization": f"Bearer aad#{os.environ['SPEECH_RESOURCE_ID']}#{token}"}


def synthesize(text: str, lang: str) -> Optional[bytes]:
    """MP3 bytes for the text, or None if Speech is not configured or the call failed (cached by text)."""
    if not configured():
        return None
    locale, voice = VOICES.get(lang, VOICES["en"])
    key = f"{voice}|{text}"
    if key in _cache:
        return _cache[key]
    import httpx

    ssml = (f"<speak version='1.0' xml:lang='{locale}'><voice name='{voice}'>"
            f"<prosody rate='-4%'>{escape(text)}</prosody></voice></speak>")
    try:
        r = httpx.post(f"https://{os.environ['SPEECH_REGION']}.tts.speech.microsoft.com/cognitiveservices/v1",
                       content=ssml.encode(), timeout=20,
                       headers={**_auth(), "Content-Type": "application/ssml+xml", "User-Agent": "inside-the-game",
                                "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3"})
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - no audio is fine, never break the app
        log.warning("Speech synthesis failed: %s", exc)
        return None
    _cache[key] = r.content
    return r.content
