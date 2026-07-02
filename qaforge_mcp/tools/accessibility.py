import json
from typing import Optional
import anthropic
from ._ai_utils import parse_json_response
from ..config import config
from ..integrations.playwright_runner import run_axe_audit

WCAG_IMPACT_SEVERITY = {
    "critical": "WCAG 2.1 Level A — must fix immediately, completely blocks users",
    "serious": "WCAG 2.1 Level A/AA — severely impacts users, fix before release",
    "moderate": "WCAG 2.1 Level AA — meaningful barrier, fix soon",
    "minor": "WCAG 2.1 Level AAA — minor issue, improve when possible",
}


async def run(url: str, component_code: str = "") -> dict:
    if component_code and not url:
        return {
            "error": "component_code analysis requires a live URL. Deploy the component and provide its URL.",
            "hint": "For static analysis of React components, consider eslint-plugin-jsx-a11y.",
        }

    if not url:
        return {"error": "url is required"}

    axe_results = await run_axe_audit(url)

    if "error" in axe_results:
        return {
            "url": url,
            "error": f"Axe audit failed: {axe_results['error']}",
            "hint": "Ensure the URL is publicly accessible from this machine.",
        }

    violations: list[dict] = axe_results.get("violations", [])
    formatted_violations = []
    for v in violations:
        nodes = v.get("nodes", [])
        affected_elements = []
        for node in nodes[:3]:
            target = node.get("target", [])
            fix_any = node.get("any", [])
            fix_hint = fix_any[0].get("message", "") if fix_any else ""
            affected_elements.append({
                "selector": str(target[0]) if target else "unknown",
                "fix_hint": fix_hint,
                "html": node.get("html", "")[:200],
            })

        formatted_violations.append({
            "rule_id": v.get("id", ""),
            "description": v.get("description", ""),
            "impact": v.get("impact", "unknown"),
            "wcag_criteria": v.get("tags", []),
            "affected_count": len(nodes),
            "affected_elements": affected_elements,
            "help_url": v.get("helpUrl", ""),
            "severity_context": WCAG_IMPACT_SEVERITY.get(v.get("impact", ""), ""),
        })

    formatted_violations.sort(key=lambda x: ["critical", "serious", "moderate", "minor"].index(x.get("impact", "minor")) if x.get("impact") in ["critical", "serious", "moderate", "minor"] else 4)

    result = {
        "url": url,
        "summary": {
            "violations": len(formatted_violations),
            "passes": axe_results.get("passes", 0),
            "incomplete": axe_results.get("incomplete", 0),
            "inapplicable": axe_results.get("inapplicable", 0),
            "compliance_level": _compliance_level(formatted_violations),
        },
        "violations": formatted_violations,
        "critical_count": sum(1 for v in formatted_violations if v["impact"] == "critical"),
        "serious_count": sum(1 for v in formatted_violations if v["impact"] == "serious"),
    }

    if config.ai_configured and formatted_violations:
        client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
        top_violations = formatted_violations[:5]
        msg = await client.messages.create(
            model=config.claude_model,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": f"""Analyze these WCAG accessibility violations and provide specific code fix suggestions.

Violations:
{json.dumps(top_violations, indent=2)}

For each violation, provide:
1. The specific code change needed
2. A before/after code example where possible
3. Priority order to fix

Format as JSON array:
[{{
  "rule_id": "...",
  "fix_code": "The actual code/attribute change",
  "example_before": "...",
  "example_after": "...",
  "priority": 1
}}]"""
            }],
        )
        raw = msg.content[0].text.strip()
        try:
            parsed, _ = parse_json_response(raw)
            result["ai_fix_suggestions"] = parsed if parsed is not None else []
        except Exception:
            result["ai_fix_suggestions_raw"] = raw

    return result


def _compliance_level(violations: list) -> str:
    if not violations:
        return "WCAG 2.1 AA Compliant"
    critical_serious = [v for v in violations if v.get("impact") in ("critical", "serious")]
    if critical_serious:
        return "Non-compliant — critical/serious violations present"
    return "Partially compliant — moderate/minor violations only"
