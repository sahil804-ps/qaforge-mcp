import json
import re


def extract_json(text: str) -> str:
    text = text.strip()

    # Strip ```json ... ``` or ``` ... ``` fences (most common case)
    fence = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if fence:
        return fence.group(1).strip()

    # Already bare JSON
    if text.startswith(("{", "[")):
        return text

    # Find outermost { } or [ ]
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end > start:
            return text[start:end + 1]

    return text


def parse_json_response(text: str) -> tuple[dict | list | None, str]:
    raw = extract_json(text)
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError:
        return None, text
