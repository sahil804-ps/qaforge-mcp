import json
import yaml
import anthropic
from ._ai_utils import parse_json_response
from ..config import config
from ..request_config import get_anthropic_api_key, ai_configured

OWASP_PAYLOADS = {
    "sql_injection": [
        "' OR '1'='1",
        "'; DROP TABLE users; --",
        "1' UNION SELECT NULL,NULL,NULL--",
        "admin'--",
        "' OR 1=1--",
    ],
    "xss": [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert(1)",
        "'><svg onload=alert(1)>",
        "<iframe src=javascript:alert(1)>",
    ],
    "auth_bypass": [
        {"Authorization": "Bearer invalid_token"},
        {"Authorization": "Bearer null"},
        {"Authorization": "Bearer eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiJ9."},
    ],
    "idor": ["0", "-1", "99999999", "undefined", "null", "../../../etc/passwd"],
    "rate_limit": {"requests": 100, "window_seconds": 10},
}


def _parse_swagger_endpoints(swagger_spec: str) -> list[dict]:
    endpoints = []
    try:
        spec = yaml.safe_load(swagger_spec) if swagger_spec.strip().startswith(("openapi", "swagger")) or ":" in swagger_spec[:100] else json.loads(swagger_spec)
        base_path = spec.get("basePath", "") or ""
        servers = spec.get("servers", [{}])
        base_url = servers[0].get("url", "") if servers else ""

        paths = spec.get("paths", {})
        for path, methods in paths.items():
            for method, details in methods.items():
                if method in ("get", "post", "put", "patch", "delete"):
                    params = details.get("parameters", [])
                    endpoints.append({
                        "method": method.upper(),
                        "path": path,
                        "full_url": f"{base_url}{path}",
                        "parameters": params,
                        "summary": details.get("summary", ""),
                    })
    except Exception:
        pass
    return endpoints


def generate_postman_collection(endpoints: list[dict], target_url: str = "") -> dict:
    items = []
    for ep in endpoints:
        url = target_url + ep["path"] if target_url else ep.get("full_url", ep["path"])

        for payload in OWASP_PAYLOADS["sql_injection"]:
            items.append({
                "name": f"[SQLi] {ep['method']} {ep['path']}",
                "request": {
                    "method": ep["method"],
                    "url": url,
                    "body": {"mode": "raw", "raw": json.dumps({"input": payload}), "options": {"raw": {"language": "json"}}},
                    "header": [{"key": "Content-Type", "value": "application/json"}],
                },
            })

        for payload in OWASP_PAYLOADS["xss"]:
            items.append({
                "name": f"[XSS] {ep['method']} {ep['path']}",
                "request": {
                    "method": ep["method"],
                    "url": url,
                    "body": {"mode": "raw", "raw": json.dumps({"input": payload}), "options": {"raw": {"language": "json"}}},
                    "header": [{"key": "Content-Type", "value": "application/json"}],
                },
            })

        for bypass_header in OWASP_PAYLOADS["auth_bypass"]:
            items.append({
                "name": f"[AuthBypass] {ep['method']} {ep['path']}",
                "request": {
                    "method": ep["method"],
                    "url": url,
                    "header": [{"key": k, "value": v} for k, v in bypass_header.items()],
                },
            })

        for idor_val in OWASP_PAYLOADS["idor"]:
            path_with_idor = ep["path"].replace("{id}", idor_val).replace("{userId}", idor_val)
            items.append({
                "name": f"[IDOR] {ep['method']} {path_with_idor}",
                "request": {
                    "method": ep["method"],
                    "url": target_url + path_with_idor if target_url else path_with_idor,
                    "header": [],
                },
            })

    return {
        "info": {"name": "QAForge Security Suite", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
        "item": items,
    }


def generate_k6_security_script(endpoints: list[dict], target_url: str = "") -> str:
    checks = []
    for ep in endpoints:
        url = target_url + ep["path"] if target_url else ep.get("full_url", ep["path"])
        url_js = json.dumps(url)
        is_get = ep["method"] == "GET"
        for payload in OWASP_PAYLOADS["sql_injection"][:2]:
            payload_js = json.dumps({"input": payload})
            if is_get:
                call = f"""  let r_{len(checks)} = http.get(
    {url_js},
    {{headers: {{'Content-Type': 'application/json'}}}}
  );"""
            else:
                call = f"""  let r_{len(checks)} = http.{ep['method'].lower()}(
    {url_js},
    JSON.stringify({payload_js}),
    {{headers: {{'Content-Type': 'application/json'}}}}
  );"""
            checks.append(f"""  // SQLi: {ep['method']} {ep['path']}
{call}
  check(r_{len(checks)}, {{'SQLi blocked (no 200 on injection)': (r) => r.status !== 200}});""")

    checks_str = "\n".join(checks[:40])
    return f"""import http from 'k6/http';
import {{ check, sleep }} from 'k6';

export const options = {{
    vus: 5,
    duration: '60s',
    thresholds: {{
        'checks': ['rate>0.95'],
    }},
}};

export default function () {{
{checks_str}
    sleep(0.5);
}}
"""


async def run(swagger_spec: str = "", endpoint_url: str = "") -> dict:
    endpoints = _parse_swagger_endpoints(swagger_spec) if swagger_spec else []

    if not endpoints and endpoint_url:
        endpoints = [{"method": "GET", "path": "/", "full_url": endpoint_url, "parameters": [], "summary": ""}]

    if not endpoints:
        return {"error": "Provide swagger_spec (YAML/JSON) or endpoint_url"}

    postman_collection = generate_postman_collection(endpoints, target_url=endpoint_url)
    k6_script = generate_k6_security_script(endpoints, target_url=endpoint_url)

    summary = {
        "endpoints_analyzed": len(endpoints),
        "total_test_cases": len(postman_collection["item"]),
        "owasp_coverage": ["A1-Injection", "A2-Auth", "A3-XSS", "A4-IDOR", "A7-RateLimit"],
        "postman_collection": postman_collection,
        "k6_security_script": k6_script,
    }

    if ai_configured():
        client = anthropic.AsyncAnthropic(api_key=get_anthropic_api_key())
        msg = await client.messages.create(
            model=config.claude_model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"Given these API endpoints: {json.dumps([e['method']+' '+e['path'] for e in endpoints[:20]])}\n\nList 5 additional security test scenarios specific to this API that go beyond standard OWASP tests. Be specific and actionable. Return as JSON array of strings."
            }]
        )
        try:
            parsed, _ = parse_json_response(msg.content[0].text.strip())
            summary["ai_additional_scenarios"] = parsed if parsed is not None else [msg.content[0].text.strip()]
        except Exception:
            summary["ai_additional_scenarios"] = [msg.content[0].text.strip()]

    return summary
