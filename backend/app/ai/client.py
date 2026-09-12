"""The one place every Gemini call goes through (see CLAUDE.md: "All AI calls go
through backend/app/ai/client.py. One place, one retry policy.").

docs/PROMPTS.md specifies gemini-2.0-flash, but that model has been retired —
Gemini's API now rejects it with a 404 pointing at gemini-3.6-flash as the
replacement, which is what's used here. (docs/PROMPTS.md and CLAUDE.md are now
stale on this point and should be updated.) Every JSON-returning call parses
defensively and retries once with a corrective nudge if parsing fails.
"""

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai

# .env lives at the repo root, not backend/ — backend/app/ai/client.py -> ai ->
# app -> backend -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

MODEL = "gemini-3.6-flash"

_client: genai.Client | None = None


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


def _strip_fences(text: str) -> str:
    """Strip a leading/trailing ``` or ```json code fence, if present."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def generate_json(prompt: str):
    """Call Gemini and parse its reply as JSON.

    Strips markdown fences, then parses. If parsing fails, retries once with a
    corrective nudge appended to the prompt ("your last output was not valid
    JSON, return only JSON"), per docs/PROMPTS.md. Raises ValueError if the
    retry also fails to parse.
    """
    raw = _get_client().models.generate_content(model=MODEL, contents=prompt).text
    try:
        return json.loads(_strip_fences(raw))
    except json.JSONDecodeError:
        pass

    nudge = (
        f"{prompt}\n\n"
        f"Your last output was not valid JSON:\n{raw}\n\n"
        "Return ONLY JSON. No markdown fences, no preamble, no explanation."
    )
    retry_raw = _get_client().models.generate_content(model=MODEL, contents=nudge).text
    try:
        return json.loads(_strip_fences(retry_raw))
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Gemini did not return valid JSON after one retry. "
            f"Last output: {retry_raw!r}"
        ) from e


def generate_text(prompt: str, history: list[dict] | None = None) -> str:
    """Conversational call, for things like the select-text AI panel.

    `history` is prior turns in chronological order, each
    {"role": "user" | "assistant", "content": str} — matching the AIMessage
    schema in docs/SCHEMA.md. `prompt` is the new user message. Returns the
    model's reply text.
    """
    genai_history = [
        {
            "role": "model" if turn["role"] == "assistant" else turn["role"],
            "parts": [{"text": turn["content"]}],
        }
        for turn in (history or [])
    ]
    chat = _get_client().chats.create(model=MODEL, history=genai_history)
    return chat.send_message(prompt).text
