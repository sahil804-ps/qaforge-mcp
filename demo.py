import asyncio
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")


async def run_demo():
    print("=" * 56)
    print("       QAFORGE MCP  --  LIVE DEMO")
    print("=" * 56)

    # ── TOOL 11: Environment Health Check ─────────────────
    print()
    print("[ TOOL 11 ]  Environment Health Check")
    print("-" * 40)
    from qaforge_mcp.tools.health_checker import run as health

    r = await health(
        {
            "GitHub API": "https://api.github.com",
            "httpbin": "https://httpbin.org/status/200",
            "JSONPlaceholder": "https://jsonplaceholder.typicode.com/posts/1",
            "Broken Svc": "http://localhost:9999",
        },
        timeout_seconds=6,
    )
    for svc in r["services"]:
        tag = "UP  " if svc["status"] == "UP" else "DOWN"
        ms = svc.get("response_time_ms", "--")
        print(f"  [{tag}]  {svc['service']:20}  {ms}ms")
    print(f"  Overall      : {r['summary']['overall_status']}")
    print(f"  Recommendation: {r['recommendation']}")

    # ── TOOL 2: Flaky Test Detection ───────────────────────
    print()
    print("[ TOOL 2 ]  Flaky Test Detection")
    print("-" * 40)
    print("  Input: 6 CI/CD runs ka JUnit XML")

    from qaforge_mcp.tools.flaky_detector import parse_junit_xml, detect_flaky

    def mk(passing):
        cases = ""
        for name, ok in passing.items():
            fail = "" if ok else '<failure message="assertion failed"/>'
            cases += f'<testcase classname="Suite" name="{name}">{fail}</testcase>'
        return f'<testsuites><testsuite name="Suite" tests="{len(passing)}">{cases}</testsuite></testsuites>'

    runs_data = [
        {"test_login": True,  "test_payment": True,  "test_cart": False, "test_signup": True},
        {"test_login": True,  "test_payment": False, "test_cart": True,  "test_signup": True},
        {"test_login": False, "test_payment": True,  "test_cart": False, "test_signup": True},
        {"test_login": True,  "test_payment": False, "test_cart": True,  "test_signup": False},
        {"test_login": True,  "test_payment": True,  "test_cart": False, "test_signup": True},
        {"test_login": True,  "test_payment": False, "test_cart": True,  "test_signup": True},
    ]
    runs = [parse_junit_xml(mk(r2)) for r2 in runs_data]
    flaky = detect_flaky(runs)
    print(f"  Tests analyzed: 4   |   Runs: 6")
    for f in flaky:
        print(
            f"  [FLAKY]  Suite.{f['test']:15}  "
            f"fail rate: {f['failure_rate']}%  "
            f"({f['failed_runs']}/{f['total_runs']} runs)"
        )

    # ── TOOL 3: Security Tests ─────────────────────────────
    print()
    print("[ TOOL 3 ]  Security Test Generation")
    print("-" * 40)
    print("  Input: Ecommerce API (Login + Users + Orders)")

    from qaforge_mcp.tools.security_tester import run as sec

    swagger = """
openapi: 3.0.0
info:
  title: Ecommerce API
  version: 1.0.0
servers:
  - url: https://api.myshop.com
paths:
  /auth/login:
    post:
      summary: Login
  /users/{id}:
    get:
      summary: Get user
  /orders/{id}:
    get:
      summary: Get order
  /products:
    get:
      summary: List products
"""
    r3 = await sec(swagger_spec=swagger)
    col = r3["postman_collection"]
    print(f"  Endpoints analyzed : {r3['endpoints_analyzed']}")
    print(f"  Total test cases   : {r3['total_test_cases']}")
    print(f"  OWASP coverage     : {r3['owasp_coverage']}")
    print(f"  Postman items      : {len(col['item'])}  (ready to import)")
    print(f"  k6 script lines    : {len(r3['k6_security_script'].splitlines())}")

    # ── TOOL 12: Test Data Generator ──────────────────────
    print()
    print("[ TOOL 12 ]  Test Data Generator")
    print("-" * 40)
    print("  Input: User + Ethereum Wallet schema")

    from qaforge_mcp.tools.data_generator import run as datagen

    schema = json.dumps(
        {
            "type": "object",
            "properties": {
                "email": {"type": "string", "format": "email"},
                "username": {"type": "string"},
                "age": {"type": "integer", "minimum": 18, "maximum": 99},
                "ethereum_address": {"type": "string"},
                "tx_hash": {"type": "string"},
            },
        }
    )
    r4 = await datagen(schema, count=4, include_edge_cases=True)
    print(f"  Valid records      : {len(r4['valid_records'])}")
    print(f"  Edge cases         : {len(r4['edge_cases'])}")
    print(f"  Blockchain fields  : {r4['summary']['blockchain_fields_detected']}")
    print()
    print("  Sample valid records:")
    for rec in r4["valid_records"]:
        print(f"    {json.dumps(rec)}")
    print()
    print("  Sample edge cases (security payloads auto-included):")
    for ec in r4["edge_cases"][:3]:
        field = ec.pop("_edge_case_field", "?")
        val = ec.pop("_edge_value", "?")
        print(f"    [{field}]  =  {val}")

    # ── TOOL 8: Regression Impact ──────────────────────────
    print()
    print("[ TOOL 8 ]  Regression Impact Analyzer")
    print("-" * 40)
    print("  PR: Switch JWT HS256->RS256 + Stripe v3")

    from qaforge_mcp.tools.regression_analyzer import _extract_changed_files

    diff = """diff --git a/src/auth/jwt_handler.py b/src/auth/jwt_handler.py
index abc..def 100644
--- a/src/auth/jwt_handler.py
+++ b/src/auth/jwt_handler.py
@@ -12 +12 @@ class JWTHandler:
-    algorithm = HS256
+    algorithm = RS256
diff --git a/src/payment/stripe.py b/src/payment/stripe.py
index 111..222 100644
--- a/src/payment/stripe.py
+++ b/src/payment/stripe.py
@@ -5 +6,15 @@ def charge():
+    stripe.PaymentIntent.create(amount=amount)
diff --git a/src/utils/logger.py b/src/utils/logger.py
index aaa..bbb 100644
--- a/src/utils/logger.py
+++ b/src/utils/logger.py
@@ -1 +1,2 @@
+    # added debug level
"""
    files = _extract_changed_files(diff)
    high_risk_words = ["auth", "payment", "billing", "security", "token", "password"]
    print(f"  Changed files: {len(files)}")
    for f in files:
        risk = "HIGH" if any(p in f["path"].lower() for p in high_risk_words) else "LOW "
        print(f"  [{risk}]  {f['path']}   +{f['additions']}/-{f['deletions']} lines")
    print()
    print("  Action: Run Login + Payment test suites before merge")

    # ── TOOL 10: Performance Baseline ─────────────────────
    print()
    print("[ TOOL 10 ]  Performance Baseline (k6)")
    print("-" * 40)
    print("  Endpoints: JSONPlaceholder API  |  5 VUs  |  15s")

    from qaforge_mcp.tools.performance_baseline import run as perf

    r6 = await perf(
        endpoints=[
            {"url": "https://jsonplaceholder.typicode.com/posts/1", "method": "GET"},
            {"url": "https://jsonplaceholder.typicode.com/users/1", "method": "GET"},
        ],
        vus=5,
        duration="15s",
        set_as_baseline=True,
    )
    m = r6.get("current_metrics", {})
    print(f"  Exit code    : {m.get('exit_code')}")
    print(f"  P50 (median) : {m.get('p50_ms', m.get('med', '--'))} ms")
    print(f"  P90          : {m.get('p90_ms', '--')} ms")
    print(f"  P95          : {m.get('p95_ms', '--')} ms")
    print(f"  Avg          : {m.get('avg_ms', '--')} ms")
    print(f"  Failure rate : {m.get('failure_rate', '--')}")
    print(f"  Baseline     : {r6.get('baseline_action')}")
    alerts = r6.get("alerts", [])
    print(f"  Alerts       : {alerts if alerts else 'None — performance OK'}")

    print()
    print("=" * 56)
    print("  DEMO COMPLETE")
    print("  6/12 tools live-tested without AI credits")
    print("  AI tools ready — add Anthropic credits to unlock")
    print("=" * 56)


asyncio.run(run_demo())
