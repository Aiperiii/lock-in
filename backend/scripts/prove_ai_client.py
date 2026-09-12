"""Proves generate_json and generate_text actually work against the real
Gemini API. Run from backend/: python3 scripts/prove_ai_client.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.client import generate_json, generate_text  # noqa: E402


def prove_generate_json() -> None:
    print("generate_json ...")
    result = generate_json(
        "Return ONLY JSON, no markdown fences: "
        '{"animal": "the name of a small mammal", "legs": <number>}'
    )
    print("  ->", result)
    assert isinstance(result, dict), "expected a JSON object"
    assert "animal" in result and "legs" in result
    print("  OK")


def prove_generate_text() -> None:
    print("generate_text ...")
    history = [
        {"role": "user", "content": "My favorite number is 7. Just acknowledge that."},
        {"role": "assistant", "content": "Got it — your favorite number is 7."},
    ]
    reply = generate_text("What number did I just tell you?", history=history)
    print("  ->", reply)
    assert "7" in reply, "expected the model to recall the number from history"
    print("  OK")


if __name__ == "__main__":
    prove_generate_json()
    print()
    prove_generate_text()
    print()
    print("Both helpers work.")
