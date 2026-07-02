import json
import anthropic
from ..config import config
from ..request_config import get_anthropic_api_key, ai_configured
from ._ai_utils import parse_json_response

SYSTEM_PROMPT = """You are a senior QA engineer and test architect with 15+ years of experience.
Generate comprehensive, production-quality test cases from specifications.
Always respond with valid JSON only — no markdown, no explanation outside JSON."""

TEST_CASE_PROMPT = """Analyze the following specification and generate a comprehensive test suite.

SPECIFICATION:
{spec}

Generate test cases covering: happy paths, negative cases, edge cases, boundary values, and security basics.

Respond with this exact JSON structure:
{{
  "test_cases": [
    {{
      "id": "TC-001",
      "title": "Descriptive test title",
      "preconditions": "What must be true before this test",
      "steps": ["Step 1: ...", "Step 2: ..."],
      "expected_result": "What should happen",
      "priority": "P1",
      "category": "functional",
      "coverage_tag": "auth/login"
    }}
  ],
  "coverage_gaps": [
    "Area not covered: e.g., OAuth flow not testable without external provider"
  ],
  "summary": {{
    "total": 0,
    "by_priority": {{"P1": 0, "P2": 0, "P3": 0}},
    "by_category": {{"functional": 0, "negative": 0, "edge": 0, "security": 0, "boundary": 0}}
  }}
}}

Priority guide: P1=critical path, P2=important, P3=nice to have.
Categories: functional, negative, edge, boundary, security, performance, integration."""


async def run(spec_content: str, swagger_spec: str = "") -> dict:
    if not ai_configured():
        return {"error": "ANTHROPIC_API_KEY not set. Cannot run AI-powered test generation."}

    combined_spec = spec_content
    if swagger_spec:
        combined_spec += f"\n\n--- SWAGGER/OPENAPI SPEC ---\n{swagger_spec}"

    client = anthropic.AsyncAnthropic(api_key=get_anthropic_api_key())
    message = await client.messages.create(
        model=config.claude_model,
        max_tokens=8096,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": TEST_CASE_PROMPT.format(spec=combined_spec[:50000])}
        ],
    )

    raw = message.content[0].text.strip()
    result, raw = parse_json_response(raw)
    try:
        if result is not None and "summary" in result and "test_cases" in result:
            result["summary"]["total"] = len(result["test_cases"])
            cats: dict = {}
            pris: dict = {}
            for tc in result["test_cases"]:
                cat = tc.get("category", "functional")
                pri = tc.get("priority", "P2")
                cats[cat] = cats.get(cat, 0) + 1
                pris[pri] = pris.get(pri, 0) + 1
            result["summary"]["by_category"] = cats
            result["summary"]["by_priority"] = pris
        return result if result is not None else {"raw_response": raw, "error": "AI returned non-JSON response."}
    except Exception:
        return {"raw_response": raw, "error": "AI returned non-JSON response. Raw content included."}
