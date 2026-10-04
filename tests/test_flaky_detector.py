import asyncio
import xml.etree.ElementTree as ET

import pytest

from qaforge_mcp.tools import flaky_detector
from qaforge_mcp.tools.flaky_detector import detect_flaky, parse_junit_xml


def junit(**tests: str) -> str:
    """Build a JUnit XML run. Values: 'pass', 'fail', or 'error'."""
    cases = []
    for name, outcome in tests.items():
        body = {"pass": "", "fail": "<failure/>", "error": "<error/>"}[outcome]
        cases.append(f'<testcase classname="suite" name="{name}">{body}</testcase>')
    return f"<testsuite>{''.join(cases)}</testsuite>"


def test_parse_junit_xml_marks_failures_and_errors():
    result = parse_junit_xml(junit(a="pass", b="fail", c="error"))
    assert result == {"suite.a": False, "suite.b": True, "suite.c": True}


def test_parse_junit_xml_raises_on_invalid_xml():
    with pytest.raises(ET.ParseError):
        parse_junit_xml("<testsuite><testcase>")


def test_detect_flaky_finds_intermittent_test_only():
    runs = [
        {"stable": False, "broken": True, "flaky": False},
        {"stable": False, "broken": True, "flaky": True},
        {"stable": False, "broken": True, "flaky": False},
        {"stable": False, "broken": True, "flaky": True},
    ]
    flaky = detect_flaky(runs)
    assert [t["test"] for t in flaky] == ["flaky"]
    assert flaky[0]["failure_rate"] == 50.0
    assert flaky[0]["failed_runs"] == 2
    assert flaky[0]["total_runs"] == 4


def test_detect_flaky_requires_minimum_runs():
    runs = [{"t": True}, {"t": False}]
    assert detect_flaky(runs) == []
    assert len(detect_flaky(runs, min_runs=2)) == 1


@pytest.mark.parametrize("failures, expected", [(1, False), (2, False), (3, True)])
def test_quarantine_recommended_above_40_percent(failures, expected):
    runs = [{"t": i < failures} for i in range(5)]
    flaky = detect_flaky(runs)
    assert flaky[0]["quarantine_recommended"] is expected


def test_detect_flaky_sorts_most_unpredictable_first():
    runs = [{"a": i < 1, "b": i < 5} for i in range(10)]
    assert [t["test"] for t in detect_flaky(runs)] == ["b", "a"]


def test_run_rejects_fewer_than_two_files():
    result = asyncio.run(flaky_detector.run([junit(a="pass")]))
    assert "error" in result


def test_run_reports_invalid_files_instead_of_ignoring_them():
    files = [junit(a="fail"), junit(a="pass"), "not xml", junit(a="fail")]
    result = asyncio.run(flaky_detector.run(files))
    assert result["total_runs"] == 3
    assert result["invalid_files"][0]["index"] == 2
    assert result["flaky_tests"][0]["test"] == "suite.a"
    assert result["quarantine_candidates"] == ["suite.a"]


def test_run_errors_when_too_few_valid_files():
    result = asyncio.run(flaky_detector.run([junit(a="pass"), "<broken"]))
    assert "error" in result
    assert len(result["invalid_files"]) == 1


def test_run_without_ai_key_explains_missing_analysis():
    files = [junit(a="fail"), junit(a="pass"), junit(a="pass")]
    result = asyncio.run(flaky_detector.run(files))
    assert "ANTHROPIC_API_KEY" in result["flaky_tests"][0]["suspected_cause"]
