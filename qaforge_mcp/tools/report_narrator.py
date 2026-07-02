import json
import xml.etree.ElementTree as ET
from typing import Optional
import anthropic
from ..config import config
from ..integrations import slack


def parse_junit(xml_content: str) -> dict:
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        return {"error": str(e)}

    total = passed = failed = skipped = 0
    failures: list[dict] = []
    modules: dict[str, dict] = {}

    for suite in root.iter("testsuite"):
        suite_name = suite.get("name", "Unknown")
        suite_total = int(suite.get("tests", 0))
        suite_failed = int(suite.get("failures", 0)) + int(suite.get("errors", 0))
        suite_skipped = int(suite.get("skipped", 0))

        total += suite_total
        failed += suite_failed
        skipped += suite_skipped
        passed += suite_total - suite_failed - suite_skipped

        modules[suite_name] = {
            "total": suite_total,
            "passed": suite_total - suite_failed - suite_skipped,
            "failed": suite_failed,
            "skipped": suite_skipped,
        }

        for tc in suite.iter("testcase"):
            failure_el = tc.find("failure") or tc.find("error")
            if failure_el is not None:
                failures.append({
                    "test": f"{tc.get('classname', '')}.{tc.get('name', '')}",
                    "message": (failure_el.get("message") or failure_el.text or "")[:300],
                    "type": failure_el.get("type", ""),
                })

    pass_rate = round((passed / total * 100) if total > 0 else 0, 1)
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "pass_rate": pass_rate,
        "failures": failures[:20],
        "modules": modules,
    }


async def run(
    current_report: str,
    previous_report: Optional[str] = None,
    send_to_slack: bool = False,
) -> dict:
    current = parse_junit(current_report)
    if "error" in current:
        try:
            current_data = json.loads(current_report)
            current = current_data
        except Exception:
            return current

    previous = None
    if previous_report:
        previous = parse_junit(previous_report)

    regression_info = ""
    if previous and "pass_rate" in previous:
        rate_diff = current.get("pass_rate", 0) - previous.get("pass_rate", 0)
        direction = "improved" if rate_diff >= 0 else "regressed"
        regression_info = f"Pass rate {direction} by {abs(rate_diff):.1f}% (was {previous['pass_rate']}%, now {current.get('pass_rate', 0)}%)."

        new_failures = []
        prev_failure_names = {f["test"] for f in previous.get("failures", [])}
        for f in current.get("failures", []):
            if f["test"] not in prev_failure_names:
                new_failures.append(f["test"])
        if new_failures:
            regression_info += f" {len(new_failures)} NEW failures: {', '.join(new_failures[:5])}."

    if config.ai_configured:
        client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
        prompt = f"""You are a QA lead writing a test report summary for stakeholders.

Current run metrics:
- Total: {current.get('total', 0)} | Passed: {current.get('passed', 0)} | Failed: {current.get('failed', 0)} | Skipped: {current.get('skipped', 0)}
- Pass rate: {current.get('pass_rate', 0)}%
- Top failures: {json.dumps([f['test'] + ': ' + f['message'][:100] for f in current.get('failures', [])[:5]])}
- Modules: {json.dumps(current.get('modules', {}))}

{f'Comparison with previous run: {regression_info}' if regression_info else ''}

Write a 3-paragraph executive summary:
1. Overall health and pass rate
2. Key failures and which modules are affected
3. Recommended actions and risk assessment

Keep it professional and concise. No bullet points — flowing paragraphs."""

        msg = await client.messages.create(
            model=config.claude_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        narrative = msg.content[0].text.strip()
    else:
        narrative = (
            f"Test run completed with {current.get('pass_rate', 0)}% pass rate. "
            f"{current.get('passed', 0)} passed, {current.get('failed', 0)} failed, {current.get('skipped', 0)} skipped. "
            + regression_info
        )

    result = {
        "narrative": narrative,
        "metrics": current,
        "regression_analysis": regression_info or "No baseline to compare against.",
        "action_required": current.get("failed", 0) > 0,
    }

    if send_to_slack and slack:
        slack_result = await slack.send_qa_report(
            summary=narrative[:500],
            pass_count=current.get("passed", 0),
            fail_count=current.get("failed", 0),
        )
        result["slack_notification"] = slack_result

    return result
