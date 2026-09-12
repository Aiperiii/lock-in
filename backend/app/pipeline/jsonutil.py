"""Defensive coercion of a Gemini JSON response into a list of dicts,
whatever shape it actually came back in (docs/PROMPTS.md asks for a bare
list, or an object with one particular key — but "asks for" isn't
"guaranteed to get")."""


def coerce_list(raw, key_hint: str | None = None) -> list[dict]:
    if isinstance(raw, list):
        return [e for e in raw if isinstance(e, dict)]
    if isinstance(raw, dict):
        if key_hint and isinstance(raw.get(key_hint), list):
            return [e for e in raw[key_hint] if isinstance(e, dict)]
        for value in raw.values():
            if isinstance(value, list):
                return [e for e in value if isinstance(e, dict)]
    return []
