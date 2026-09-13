"""The one place every Gemini call goes through (see CLAUDE.md: "All AI calls go
through backend/app/ai/client.py. One place, one retry policy.").

docs/PROMPTS.md specifies gemini-2.0-flash, but that model has been retired —
Gemini's API now rejects it with a 404. Two replacement tiers are used instead,
picked per call site by how much volume it needs:

- MODEL_QUALITY (gemini-3.7-flash): better judgment, but only 20 requests/day
  on the free tier — fine for something that runs once per book (e.g. chapter
  detection), not for anything called per-lesson or per-question. (Originally
  gemini-3.6-flash; swapped after that tier's daily quota ran out mid-session —
  same 20/day cap, just a fresh, unused bucket.)
- MODEL_FAST (gemini-3.5-flash-lite): 15 RPM / 250K TPM / 500 requests/day on
  the free tier — the default, for high-volume call sites.

(docs/PROMPTS.md and CLAUDE.md are now stale on the model name and should be
updated.) Every JSON-returning call parses defensively and retries once with a
corrective nudge if parsing fails. A 429 (rate limit) on either tier retries
with exponential backoff, then falls back to the other tier once; if that is
also rate-limited, GeminiUnavailable is raised — callers should treat that as
an infrastructure failure (e.g. mark a book `failed`), not a content issue.
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# .env lives at the repo root, not backend/ — backend/app/ai/client.py -> ai ->
# app -> backend -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

MODEL_QUALITY = "gemini-3.7-flash"
MODEL_FAST = "gemini-3.5-flash-lite"
DEFAULT_MODEL = MODEL_FAST

_OTHER_TIER = {MODEL_QUALITY: MODEL_FAST, MODEL_FAST: MODEL_QUALITY}

RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 2

_client: genai.Client | None = None


class GeminiUnavailable(Exception):
    """Both model tiers are rate-limited after retrying. This is an
    infrastructure failure, not a content issue — callers should surface it
    (e.g. mark a book `failed` with a readable stage) rather than silently
    degrade the way a bad-JSON response would."""


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"GEMINI_API_KEY is not set. Expected it in {REPO_ROOT / '.env'}"
            )
        _client = genai.Client(api_key=api_key)
    return _client


def _is_rate_limited(exc: Exception) -> bool:
    return isinstance(exc, genai_errors.APIError) and exc.code == 429


def _with_retry_and_fallback(model: str, call: Callable[[str], str]) -> str:
    """Runs `call(model)`, retrying on a 429 with exponential backoff, then
    falling back to the other tier once if backoff never clears it."""
    delay = RETRY_BASE_DELAY_SECONDS
    last_exc: Exception | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return call(model)
        except Exception as exc:
            if not _is_rate_limited(exc):
                raise
            last_exc = exc
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(delay)
                delay *= 2

    fallback_model = _OTHER_TIER.get(model)
    if fallback_model:
        try:
            return call(fallback_model)
        except Exception as exc:
            if not _is_rate_limited(exc):
                raise
            last_exc = exc

    raise GeminiUnavailable(
        f"Both {model} and its fallback are rate-limited: {last_exc}"
    ) from last_exc


def _strip_fences(text: str) -> str:
    """Strip a leading/trailing ``` or ```json code fence, if present."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def generate_json(prompt: str, model: str = DEFAULT_MODEL):
    """Call Gemini and parse its reply as JSON.

    Strips markdown fences, then parses. If parsing fails, retries once with a
    corrective nudge appended to the prompt ("your last output was not valid
    JSON, return only JSON"), per docs/PROMPTS.md. Raises ValueError if the
    retry also fails to parse; raises GeminiUnavailable if both model tiers
    are rate-limited.
    """

    def call(m: str) -> str:
        return _get_client().models.generate_content(model=m, contents=prompt).text

    raw = _with_retry_and_fallback(model, call)
    logger.info("generate_json(%s): raw response (%d chars): %.2000r", model, len(raw), raw)
    try:
        return json.loads(_strip_fences(raw))
    except json.JSONDecodeError:
        pass

    nudge = (
        f"{prompt}\n\n"
        f"Your last output was not valid JSON:\n{raw}\n\n"
        "Return ONLY JSON. No markdown fences, no preamble, no explanation."
    )

    def retry_call(m: str) -> str:
        return _get_client().models.generate_content(model=m, contents=nudge).text

    retry_raw = _with_retry_and_fallback(model, retry_call)
    logger.info(
        "generate_json(%s): raw retry response (%d chars): %.2000r", model, len(retry_raw), retry_raw
    )
    try:
        return json.loads(_strip_fences(retry_raw))
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Gemini did not return valid JSON after one retry. "
            f"Last output: {retry_raw!r}"
        ) from e


def generate_text(
    prompt: str,
    history: list[dict] | None = None,
    system_instruction: str | None = None,
    model: str = DEFAULT_MODEL,
) -> str:
    """Conversational call, for things like the select-text AI panel.

    `history` is prior turns in chronological order, each
    {"role": "user" | "assistant", "content": str} — matching the AIMessage
    schema in docs/SCHEMA.md. `prompt` is the new user message.
    `system_instruction` (e.g. docs/PROMPTS.md section 7's anchoring prompt)
    is kept out of the visible turn history — it's call-site framing, not a
    message either party said — and is re-sent on every call in a thread
    since each call opens a fresh chat session seeded with the stored
    history rather than holding a live session across requests. Returns the
    model's reply text. Raises GeminiUnavailable if both model tiers are
    rate-limited.
    """
    genai_history = [
        {
            "role": "model" if turn["role"] == "assistant" else turn["role"],
            "parts": [{"text": turn["content"]}],
        }
        for turn in (history or [])
    ]
    config = (
        genai_types.GenerateContentConfig(system_instruction=system_instruction)
        if system_instruction
        else None
    )

    def call(m: str) -> str:
        chat = _get_client().chats.create(model=m, history=genai_history, config=config)
        return chat.send_message(prompt).text

    return _with_retry_and_fallback(model, call)
