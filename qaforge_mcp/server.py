import json
from typing import Optional, Union
from fastmcp import FastMCP

from .tools import (
    test_generator,
    flaky_detector,
    security_tester,
    report_narrator,
    browser_differ,
    test_executor,
    bug_reporter,
    regression_analyzer,
    accessibility,
    performance_baseline,
    health_checker,
    data_generator,
)

mcp = FastMCP(
    name="QAForge MCP",
    instructions=(
        "QAForge MCP is an all-in-one QA engineering MCP server. "
        "It provides 12 specialized QA tools covering test generation, security testing, "
        "flaky test detection, cross-browser diffing, accessibility audits, performance baselines, "
        "bug reporting, regression impact analysis, and more. "
        "Use these tools to automate your entire QA workflow from a single natural language prompt."
    ),
)


# ─── Tool 1: generate_test_cases ─────────────────────────────────────────────


@mcp.tool()
async def generate_test_cases(
    frd_content: str,
    swagger_spec: str = "",
) -> str:
    """Generate comprehensive test cases from an FRD document or Swagger/OpenAPI spec using AI.

    Produces numbered test cases with ID, title, preconditions, steps, expected result,
    priority (P1/P2/P3), category, and coverage tags. Also identifies coverage gaps.

    Args:
        frd_content: Feature requirements document, user story, or API description text.
        swagger_spec: Optional Swagger/OpenAPI YAML or JSON spec for additional context.

    Returns:
        JSON with test_cases array, coverage_gaps list, and summary statistics.
    """
    result = await test_generator.run(frd_content, swagger_spec)
    return json.dumps(result, indent=2)


# ─── Tool 2: detect_flaky_tests ──────────────────────────────────────────────


@mcp.tool()
async def detect_flaky_tests(
    junit_xml_files: list[str],
) -> str:
    """Detect flaky tests by analyzing multiple JUnit XML test run files statistically.

    A test is considered flaky if it fails between 10% and 90% of runs (not consistently
    passing or failing). Uses AI to classify root causes: race_condition, timing,
    shared_state, external_dependency, data_pollution, or environment.

    Args:
        junit_xml_files: List of JUnit XML content strings from multiple CI/CD runs.
                         Provide at least 5-10 runs for meaningful analysis.

    Returns:
        JSON with flaky_tests list (failure_rate, suspected_cause, fix_suggestion,
        quarantine_recommended), total analyzed, and quarantine_candidates list.
    """
    result = await flaky_detector.run(junit_xml_files)
    return json.dumps(result, indent=2)


# ─── Tool 3: generate_security_tests ─────────────────────────────────────────


@mcp.tool()
async def generate_security_tests(
    swagger_spec: str = "",
    endpoint_url: str = "",
) -> str:
    """Generate an OWASP Top 10 aligned security test suite for your API.

    Produces a ready-to-import Postman collection and a k6 security script covering:
    SQL injection, XSS, auth bypass (including JWT none-algorithm), IDOR, and rate limiting.
    Also uses AI to suggest API-specific additional security scenarios.

    Args:
        swagger_spec: Swagger/OpenAPI YAML or JSON spec (preferred for full coverage).
        endpoint_url: Single API base URL (used if swagger_spec not provided).

    Returns:
        JSON with postman_collection, k6_security_script, owasp_coverage, and
        ai_additional_scenarios.
    """
    result = await security_tester.run(swagger_spec, endpoint_url)
    return json.dumps(result, indent=2)


# ─── Tool 4: narrate_report ──────────────────────────────────────────────────


@mcp.tool()
async def narrate_report(
    current_report: str,
    previous_report: str = "",
    send_to_slack: bool = False,
) -> str:
    """Convert a JUnit XML or Allure JSON test report into a stakeholder-ready narrative.

    Extracts pass/fail metrics, compares against previous sprint baseline, identifies
    regressions and new failures, and generates a professional 3-paragraph executive summary.

    Args:
        current_report: JUnit XML string from the current test run.
        previous_report: Optional JUnit XML from a previous run for regression comparison.
        send_to_slack: If True and SLACK_WEBHOOK is configured, posts summary to Slack.

    Returns:
        JSON with narrative (natural language summary), metrics, regression_analysis,
        and action_required flag.
    """
    result = await report_narrator.run(current_report, previous_report or None, send_to_slack)
    return json.dumps(result, indent=2)


# ─── Tool 5: diff_browsers ───────────────────────────────────────────────────


@mcp.tool()
async def diff_browsers(
    url: str,
    scenario_description: str = "",
) -> str:
    """Run a URL across Chrome, Firefox, and Safari (WebKit) and diff the results.

    Detects cross-browser differences including: page title mismatches, DOM size variance,
    JavaScript errors, slow load times (>5s), and browser-specific render failures.
    Requires Playwright browsers installed: npx playwright install chromium firefox webkit

    Args:
        url: The URL to test across all three browsers.
        scenario_description: Optional description of what to test (for context in report).

    Returns:
        JSON with overall_severity (pass/warning/critical), diffs list, and per-browser
        results including performance timing and JS errors.
    """
    result = await browser_differ.run(url, scenario_description)
    return json.dumps(result, indent=2)


# ─── Tool 6: ai_test_executor ────────────────────────────────────────────────


@mcp.tool()
async def ai_test_executor(
    test_cases: Union[str, list],
    target_url: str,
) -> str:
    """Execute structured test cases automatically against a live URL using Playwright.

    Parses test cases from JSON list or structured text, then executes each test's steps.
    Supports step types: click, fill...with, assert visible, assert text, navigate.

    Args:
        test_cases: JSON list of test case objects, or structured text with steps.
                    Each case: {id, title, steps: [...], expected_result}.
        target_url: Base URL of the environment to test against.

    Returns:
        JSON with summary (total/passed/failed/pass_rate), full test_results list,
        and failed_tests with error details.
    """
    result = await test_executor.run(test_cases, target_url)
    return json.dumps(result, indent=2)


# ─── Tool 7: bug_report_generator ────────────────────────────────────────────


@mcp.tool()
async def bug_report_generator(
    test_failure: str,
    logs: str = "",
    environment: str = "staging",
    create_jira_ticket: bool = True,
) -> str:
    """Generate a structured bug report from a test failure and optionally create a Jira ticket.

    Uses AI to analyze the failure, infer severity, suggest root cause, write reproduction
    steps, and format everything into a Jira-ready bug report. Automatically creates a
    Jira issue if JIRA_URL, JIRA_EMAIL, and JIRA_TOKEN are configured.

    Args:
        test_failure: Description or error message of the failed test.
        logs: Stack trace, error logs, or additional context.
        environment: Environment where failure occurred (staging, prod, dev).
        create_jira_ticket: If True, creates a Jira issue automatically.

    Returns:
        JSON with bug_report (AI-structured), formatted_report (readable text),
        and jira_ticket (key, id, url) if Jira is configured.
    """
    result = await bug_reporter.run(test_failure, logs, environment, create_jira_ticket)
    return json.dumps(result, indent=2)


# ─── Tool 8: regression_impact_analyzer ──────────────────────────────────────


@mcp.tool()
async def regression_impact_analyzer(
    git_diff: str,
    test_suite_description: str = "",
    pr_title: str = "",
) -> str:
    """Analyze a git diff to identify which test areas are impacted before merging a PR.

    Parses changed files, identifies high-risk modules (auth, payment, database, etc.),
    and uses AI to map code changes to specific test areas with risk levels and
    recommended tests to run before merge.

    Args:
        git_diff: Output of 'git diff main...HEAD' or 'git diff HEAD~1'.
        test_suite_description: Optional description of your test suite for better mapping.
        pr_title: Optional PR title for additional context.

    Returns:
        JSON with risk_assessment per file, impact_analysis (AI-powered), must_run_before_merge
        list, and execution_priority ordering.
    """
    result = await regression_analyzer.run(git_diff, test_suite_description, pr_title)
    return json.dumps(result, indent=2)


# ─── Tool 9: accessibility_checker ───────────────────────────────────────────


@mcp.tool()
async def accessibility_checker(
    url: str,
    component_code: str = "",
) -> str:
    """Audit a URL for WCAG 2.1 accessibility violations using axe-core via Playwright.

    Injects axe-core into the live page and runs a full accessibility audit. Violations
    are sorted by severity (critical → serious → moderate → minor) with element selectors,
    WCAG criteria tags, and AI-generated code fix suggestions for the top violations.

    Args:
        url: URL of the page to audit (must be accessible from this machine).
        component_code: Optional React/HTML component code for additional context in fixes.

    Returns:
        JSON with violations (sorted by severity), summary (compliance level, counts),
        and ai_fix_suggestions with before/after code examples.
    """
    result = await accessibility.run(url, component_code)
    return json.dumps(result, indent=2)


# ─── Tool 10: performance_baseline_mcp ───────────────────────────────────────


@mcp.tool()
async def performance_baseline_mcp(
    endpoints: list[dict],
    vus: int = 10,
    duration: str = "30s",
    set_as_baseline: bool = False,
) -> str:
    """Run a k6 load test, capture P50/P90/P95/P99 metrics, and compare against baseline.

    Generates and executes a k6 load test script for the specified endpoints. On first run,
    establishes a performance baseline. On subsequent runs, compares and alerts if P90/P95
    degrades more than 20% from baseline.

    Requires k6 installed: https://k6.io/docs/getting-started/installation/

    Args:
        endpoints: List of endpoint dicts: [{url, method?, headers?, body?}].
        vus: Number of virtual users (concurrent).
        duration: Test duration string (e.g., '30s', '2m', '5m').
        set_as_baseline: If True, saves current results as the new baseline.

    Returns:
        JSON with current_metrics (P50/P90/P95/P99/avg/rps), baseline_comparison,
        alerts for regressions, and the generated k6_script.
    """
    result = await performance_baseline.run(endpoints, vus, duration, set_as_baseline)
    return json.dumps(result, indent=2)


# ─── Tool 11: environment_health_checker ─────────────────────────────────────


@mcp.tool()
async def environment_health_checker(
    service_urls: dict[str, str],
    alert_on_failure: bool = False,
    timeout_seconds: float = 10.0,
) -> str:
    """Check the health of all services in your test environment before running tests.

    HTTP GETs each service URL, measures response time, checks status codes, and
    determines UP/DEGRADED/DOWN status. Blocks test runs against broken environments.
    Can send Slack alerts when services are down.

    Args:
        service_urls: Dict of service name → URL. Example:
                      {"API": "http://api.staging.com/health", "Auth": "http://auth.staging.com/ping"}
        alert_on_failure: If True and SLACK_WEBHOOK is set, sends Slack alert on DOWN services.
        timeout_seconds: Per-service request timeout in seconds.

    Returns:
        JSON with summary (overall_status, counts), per-service results (status, response_time_ms),
        safe_to_run_tests flag, and recommendation.
    """
    result = await health_checker.run(service_urls, alert_on_failure, timeout_seconds)
    return json.dumps(result, indent=2)


# ─── Tool 12: test_data_generator ────────────────────────────────────────────


@mcp.tool()
async def test_data_generator(
    schema: str,
    count: int = 10,
    domain: str = "general",
    include_edge_cases: bool = True,
) -> str:
    """Generate realistic test data from a JSON Schema or natural language description.

    Produces valid records using Faker for realistic values, plus edge cases (empty strings,
    SQL injection payloads, boundary values, null values). Includes special generators for
    blockchain domains: Ethereum addresses, transaction hashes, wallet keys, ENS names.

    Args:
        schema: JSON Schema object string, or natural language description (requires ANTHROPIC_API_KEY).
        count: Number of valid test records to generate (max 100).
        domain: Hint for data domain: 'general', 'blockchain', 'ecommerce', 'healthcare', etc.
        include_edge_cases: If True, generates edge case records alongside valid ones.

    Returns:
        JSON with valid_records list, edge_cases list, schema_fields detected,
        and blockchain_fields_detected if applicable.
    """
    result = await data_generator.run(schema, count, domain, include_edge_cases)
    return json.dumps(result, indent=2)
