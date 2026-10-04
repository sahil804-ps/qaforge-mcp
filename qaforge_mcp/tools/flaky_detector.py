import json
import xml.etree.ElementTree as ET
from ._ai_utils import parse_json_response
from collections import defaultdict
import anthropic
from ..config import config
from ..request_config import get_anthropic_api_key, ai_configured

MIN_RUNS_PER_TEST = 3
QUARANTINE_FAILURE_RATE = 40.0


def parse_junit_xml(xml_content: str) -> dict[str, bool]:
    """Parse a single JUnit XML and return {test_name: failed}.

    Raises ET.ParseError if the content is not valid XML.
    """
    results: dict[str, bool] = {}
    root = ET.fromstring(xml_content)
    for tc in root.iter("testcase"):
        classname = tc.get("classname", "Unknown")
        name = tc.get("name", "Unknown")
        full_name = f"{classname}.{name}"
        failed = tc.find("failure") is not None or tc.find("error") is not None
        results[full_name] = failed
    return results


def detect_flaky(
    runs: list[dict[str, bool]],
    threshold_low: float = 0.10,
    threshold_high: float = 0.90,
    min_runs: int = MIN_RUNS_PER_TEST,
) -> list[dict]:
    """
    Tests with failure rate between threshold_low and threshold_high across runs are flaky.
    Consistently failing (>90%) or consistently passing (<10%) are not flaky.
    Tests seen in fewer than min_runs runs are skipped: one failure in two runs is not evidence.
    """
    test_failures: dict[str, list[bool]] = defaultdict(list)
    for run in runs:
        for test_name, failed in run.items():
            test_failures[test_name].append(failed)

    flaky: list[dict] = []
    for test_name, failure_history in test_failures.items():
        if len(failure_history) < min_runs:
            continue
        fail_rate = sum(failure_history) / len(failure_history)
        if threshold_low <= fail_rate <= threshold_high:
            failure_rate = round(fail_rate * 100, 1)
            flaky.append({
                "test": test_name,
                "failure_rate": failure_rate,
                "failed_runs": sum(failure_history),
                "total_runs": len(failure_history),
                "quarantine_recommended": failure_rate > QUARANTINE_FAILURE_RATE,
            })

    flaky.sort(key=lambda x: abs(x["failure_rate"] - 50))
    return flaky


async def classify_root_causes(flaky_tests: list[dict]) -> list[dict]:
    if not ai_configured() or not flaky_tests:
        for t in flaky_tests:
            t["suspected_cause"] = "unknown — set ANTHROPIC_API_KEY for AI analysis"
            t["fix_suggestion"] = "Investigate timing, shared state, and external dependencies"
        return flaky_tests

    client = anthropic.AsyncAnthropic(api_key=get_anthropic_api_key())
    prompt = f"""You are a QA expert analyzing flaky tests. For each test below, suggest the most likely root cause and fix.

Flaky tests:
{json.dumps(flaky_tests, indent=2)}

Respond with JSON — same list with two extra fields per item:
- "suspected_cause": one of "race_condition", "timing", "shared_state", "external_dependency", "data_pollution", "environment", "unknown"
- "fix_suggestion": one concrete fix sentence

Return only the JSON array."""

    message = await client.messages.create(
        model=config.claude_model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    parsed, _ = parse_json_response(raw)
    if not isinstance(parsed, list):
        return flaky_tests

    by_name = {t["test"]: t for t in flaky_tests}
    for item in parsed:
        if isinstance(item, dict) and item.get("test") in by_name:
            target = by_name[item["test"]]
            target["suspected_cause"] = item.get("suspected_cause", "unknown")
            target["fix_suggestion"] = item.get("fix_suggestion", "")
    return flaky_tests


async def run(junit_xml_files: list[str]) -> dict:
    if len(junit_xml_files) < 2:
        return {"error": "Provide at least 2 JUnit XML strings in junit_xml_files list"}

    runs: list[dict[str, bool]] = []
    invalid_files: list[dict] = []
    for index, xml in enumerate(junit_xml_files):
        try:
            runs.append(parse_junit_xml(xml))
        except ET.ParseError as e:
            invalid_files.append({"index": index, "error": str(e)})

    if len(runs) < 2:
        return {
            "error": "Fewer than 2 valid JUnit XML files after parsing",
            "invalid_files": invalid_files,
        }

    flaky = detect_flaky(runs)

    all_tests = set()
    for r in runs:
        all_tests.update(r.keys())

    if not flaky:
        return {
            "flaky_tests": [],
            "total_tests_analyzed": len(all_tests),
            "total_runs": len(runs),
            "invalid_files": invalid_files,
            "message": "No flaky tests detected. All tests are consistent.",
        }

    enriched = await classify_root_causes(flaky)

    return {
        "flaky_tests": enriched,
        "flaky_count": len(enriched),
        "total_tests_analyzed": len(all_tests),
        "total_runs": len(runs),
        "invalid_files": invalid_files,
        "quarantine_candidates": [t["test"] for t in enriched if t.get("quarantine_recommended")],
    }
