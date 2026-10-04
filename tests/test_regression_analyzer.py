import asyncio

import pytest

from qaforge_mcp.tools import regression_analyzer
from qaforge_mcp.tools.regression_analyzer import _extract_changed_files, _is_test_file


def diff_for(path: str, added: int = 1, removed: int = 0, hunk: str = "def handler():") -> str:
    lines = [
        f"diff --git a/{path} b/{path}",
        f"--- a/{path}",
        f"+++ b/{path}",
        f"@@ -1,3 +1,4 @@ {hunk}",
    ]
    lines += ["+new line"] * added
    lines += ["-old line"] * removed
    return "\n".join(lines)


def test_extract_changed_files_counts_lines_and_functions():
    diff = diff_for("src/app.py", added=3, removed=2) + "\n" + diff_for("README.md", hunk="")
    files = _extract_changed_files(diff)
    assert [f["path"] for f in files] == ["src/app.py", "README.md"]
    assert files[0]["additions"] == 3
    assert files[0]["deletions"] == 2
    assert files[0]["changed_functions"] == ["def handler():"]
    assert files[1]["changed_functions"] == []


def test_extract_changed_files_ignores_file_header_lines():
    files = _extract_changed_files(diff_for("a.py", added=0, removed=0))
    assert files[0]["additions"] == 0
    assert files[0]["deletions"] == 0


@pytest.mark.parametrize(
    "path",
    [
        "tests/test_auth.py",
        "src/__tests__/login.js",
        "pkg/payment_test.go",
        "web/checkout.spec.ts",
        "web/Button.test.tsx",
        "test_utils.py",
    ],
)
def test_is_test_file_true(path):
    assert _is_test_file(path)


@pytest.mark.parametrize(
    "path",
    ["src/latest_payment.py", "billing/attestation.py", "src/contest/admin.py", "inspector.py"],
)
def test_is_test_file_false_for_names_that_merely_contain_test(path):
    assert not _is_test_file(path)


def analyze(diff: str) -> dict:
    return asyncio.run(regression_analyzer.run(diff))


def test_payment_file_containing_test_substring_stays_high_risk():
    result = analyze(diff_for("src/latest_payment.py"))
    assert result["risk_assessment"][0]["risk"] == "high"


def test_large_change_is_high_risk():
    result = analyze(diff_for("src/utils.py", added=80, removed=30))
    assert result["risk_assessment"][0]["risk"] == "high"


def test_test_file_is_low_risk_even_in_auth_module():
    result = analyze(diff_for("tests/test_auth.py"))
    assessment = result["risk_assessment"][0]
    assert assessment["risk"] == "low"
    assert assessment["reasons"] == ["Test file — usually lower impact"]


def test_unparseable_diff_returns_error():
    assert "error" in analyze("not a diff")


def test_non_dict_ai_response_does_not_crash(monkeypatch):
    class FakeMessages:
        async def create(self, **kwargs):
            class Block:
                text = "I could not analyze this diff."

            class Msg:
                content = [Block()]

            return Msg()

    class FakeClient:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

    monkeypatch.setattr(regression_analyzer, "ai_configured", lambda: True)
    monkeypatch.setattr(regression_analyzer, "get_anthropic_api_key", lambda: "test-key")
    monkeypatch.setattr(regression_analyzer.anthropic, "AsyncAnthropic", FakeClient)

    result = analyze(diff_for("src/auth.py"))
    assert result["impact_analysis_raw"] == "I could not analyze this diff."
