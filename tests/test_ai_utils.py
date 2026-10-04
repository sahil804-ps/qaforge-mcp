import pytest

from qaforge_mcp.tools._ai_utils import extract_json, parse_json_response


@pytest.mark.parametrize(
    "text, expected",
    [
        ('{"a": 1}', '{"a": 1}'),
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ('```\n[1, 2]\n```', "[1, 2]"),
        ('Here you go: {"a": 1} hope it helps', '{"a": 1}'),
        ("Result: [1, 2, 3].", "[1, 2, 3]"),
    ],
)
def test_extract_json(text, expected):
    assert extract_json(text) == expected


def test_parse_json_response_valid():
    parsed, raw = parse_json_response('```json\n{"ok": true}\n```')
    assert parsed == {"ok": True}
    assert raw == '{"ok": true}'


def test_parse_json_response_invalid_returns_none_and_original_text():
    text = "Sorry, I can't produce JSON for that."
    parsed, raw = parse_json_response(text)
    assert parsed is None
    assert raw == text
