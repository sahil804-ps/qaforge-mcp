import json
import re
import anthropic
from ._ai_utils import parse_json_response
from ..config import config
from ..request_config import get_anthropic_api_key, ai_configured

_TEST_FILE_RE = re.compile(
    r"(^|/)(tests?|specs?|__tests__|__mocks__|mocks?)/"
    r"|(^|/)test_[^/]+$"
    r"|_test\.[^/]+$"
    r"|\.(test|spec)\.[^/]+$"
)


def _is_test_file(path: str) -> bool:
    return bool(_TEST_FILE_RE.search(path.lower().replace("\\", "/")))


def _extract_changed_files(git_diff: str) -> list[dict]:
    files = []
    current_file = None
    additions = deletions = 0

    for line in git_diff.splitlines():
        if line.startswith("diff --git"):
            if current_file:
                files.append({**current_file, "additions": additions, "deletions": deletions})
            additions = deletions = 0
            match = re.search(r"b/(.+)$", line)
            current_file = {"path": match.group(1) if match else line, "changed_functions": []}
        elif line.startswith("@@"):
            match = re.search(r"@@[^@]+@@\s*(.+)?", line)
            if match and match.group(1):
                func_hint = match.group(1).strip()[:80]
                if func_hint and current_file:
                    current_file["changed_functions"].append(func_hint)
        elif line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1

    if current_file:
        files.append({**current_file, "additions": additions, "deletions": deletions})

    return files


async def run(
    git_diff: str,
    test_suite_description: str = "",
    pr_title: str = "",
) -> dict:
    changed_files = _extract_changed_files(git_diff)

    if not changed_files:
        return {"error": "Could not parse git diff. Provide output of 'git diff main...HEAD'"}

    high_risk_patterns = [
        "auth", "payment", "billing", "checkout", "security", "token",
        "password", "permission", "admin", "database", "migration", "schema",
    ]

    risk_assessment = []
    for f in changed_files:
        path_lower = f["path"].lower()
        risk = "low"
        risk_reasons = []

        if any(p in path_lower for p in high_risk_patterns):
            risk = "high"
            matched = [p for p in high_risk_patterns if p in path_lower]
            risk_reasons.append(f"High-risk module: {', '.join(matched)}")

        if f.get("additions", 0) + f.get("deletions", 0) > 100:
            risk = "high"
            risk_reasons.append(f"Large change: +{f['additions']}/-{f['deletions']} lines")

        if _is_test_file(f["path"]):
            risk = "low"
            risk_reasons = ["Test file — usually lower impact"]

        risk_assessment.append({
            "file": f["path"],
            "risk": risk,
            "reasons": risk_reasons,
            "additions": f.get("additions", 0),
            "deletions": f.get("deletions", 0),
            "changed_functions": f.get("changed_functions", [])[:5],
        })

    result = {
        "changed_files": len(changed_files),
        "pr_title": pr_title,
        "risk_assessment": risk_assessment,
        "high_risk_files": [r for r in risk_assessment if r["risk"] == "high"],
    }

    if ai_configured():
        client = anthropic.AsyncAnthropic(api_key=get_anthropic_api_key())
        prompt = f"""You are a QA engineer performing regression impact analysis for a code change.

PR Title: {pr_title or 'N/A'}
Changed files summary:
{json.dumps([{'file': r['file'], 'risk': r['risk'], 'changes': r['additions'] + r['deletions'], 'functions': r['changed_functions']} for r in risk_assessment], indent=2)}

{f'Test Suite Context: {test_suite_description}' if test_suite_description else ''}

Analyze which test areas are impacted and respond with JSON:
{{
  "impacted_test_areas": [
    {{
      "area": "Test area name (e.g., Login Flow, Payment Processing)",
      "reason": "Why this area is impacted",
      "risk_level": "high|medium|low",
      "recommended_tests": ["TC-001: ...", "TC-002: ..."],
      "must_run_before_merge": true
    }}
  ],
  "execution_priority": ["Area 1 (run first)", "Area 2", "Area 3"],
  "estimated_test_time_minutes": 0,
  "recommendation": "Overall recommendation for this PR's test strategy"
}}"""

        msg = await client.messages.create(
            model=config.claude_model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        ai_analysis, _ = parse_json_response(raw)
        if isinstance(ai_analysis, dict):
            result["impact_analysis"] = ai_analysis
            result["must_run_before_merge"] = [
                area for area in ai_analysis.get("impacted_test_areas", [])
                if isinstance(area, dict) and area.get("must_run_before_merge")
            ]
        else:
            result["impact_analysis_raw"] = raw
    else:
        result["impact_analysis"] = {
            "recommendation": f"Set ANTHROPIC_API_KEY for AI-powered impact analysis. {len([r for r in risk_assessment if r['risk'] == 'high'])} high-risk files detected."
        }

    return result
