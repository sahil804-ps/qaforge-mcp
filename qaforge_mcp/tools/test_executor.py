import json
import time
from typing import Union
from ..integrations.playwright_runner import execute_steps


def _parse_test_cases(test_cases_input: Union[str, list]) -> list[dict]:
    if isinstance(test_cases_input, list):
        return test_cases_input

    try:
        parsed = json.loads(test_cases_input)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and "test_cases" in parsed:
            return parsed["test_cases"]
    except (json.JSONDecodeError, TypeError):
        pass

    cases = []
    lines = test_cases_input.strip().splitlines()
    current: dict | None = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("TC-") or (stripped and stripped[0].isdigit() and ". " in stripped):
            if current:
                cases.append(current)
            current = {"id": stripped.split(" ")[0], "title": stripped, "steps": [], "expected_result": ""}
        elif current and stripped.startswith("Step") or stripped.startswith("-"):
            current["steps"].append(stripped.lstrip("-• "))
        elif current and stripped.lower().startswith("expected"):
            current["expected_result"] = stripped
    if current:
        cases.append(current)
    return cases


async def run(test_cases: Union[str, list], target_url: str) -> dict:
    if not target_url:
        return {"error": "target_url is required"}

    cases = _parse_test_cases(test_cases)
    if not cases:
        return {"error": "Could not parse test_cases. Provide a JSON list or structured text."}

    results: list[dict] = []
    passed = failed = 0

    for tc in cases:
        tc_id = tc.get("id", f"TC-{len(results)+1:03d}")
        title = tc.get("title", "Unnamed test")
        steps = tc.get("steps", [])
        expected = tc.get("expected_result", "")

        start = time.monotonic()
        exec_result = await execute_steps(target_url, steps)
        duration_ms = round((time.monotonic() - start) * 1000)

        step_results = exec_result.get("steps", [])
        tc_failed = any(s.get("status") == "fail" for s in step_results)
        tc_status = "fail" if tc_failed else "pass"

        if tc_status == "pass":
            passed += 1
        else:
            failed += 1

        fail_details = [s for s in step_results if s.get("status") == "fail"]
        results.append({
            "id": tc_id,
            "title": title,
            "status": tc_status,
            "duration_ms": duration_ms,
            "steps_executed": len(step_results),
            "failed_step": fail_details[0] if fail_details else None,
            "expected_result": expected,
            "final_url": exec_result.get("final_url", ""),
        })

    total = passed + failed
    return {
        "target_url": target_url,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
        },
        "test_results": results,
        "failed_tests": [r for r in results if r["status"] == "fail"],
    }
