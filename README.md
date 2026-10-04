# QAForge MCP

An all-in-one QA engineering MCP server — 12 QA tools for Claude Code, in one place.

Generate test cases, run security scans, detect flaky tests, diff browsers, check accessibility, baseline performance, and more — all from natural language, inside Claude.

## Tools

| # | Tool | What it does |
|---|------|---------------|
| 1 | `generate_test_cases` | FRD/Swagger → numbered test cases with priority + coverage gaps |
| 2 | `detect_flaky_tests` | Statistical flaky-test detection across JUnit XML runs, AI root-cause |
| 3 | `generate_security_tests` | OWASP Top 10 Postman collection + k6 security script |
| 4 | `narrate_report` | JUnit/Allure report → stakeholder-ready narrative, optional Slack post |
| 5 | `diff_browsers` | Cross-browser (Chrome/Firefox/WebKit) diffing via Playwright |
| 6 | `ai_test_executor` | Executes structured test cases against a live URL |
| 7 | `bug_report_generator` | AI bug report + optional Jira ticket creation |
| 8 | `regression_impact_analyzer` | git diff → impacted test areas + risk levels |
| 9 | `accessibility_checker` | WCAG 2.1 audit via axe-core, AI fix suggestions |
| 10 | `performance_baseline_mcp` | k6 load test, P50–P99, baseline regression alerts |
| 11 | `environment_health_checker` | Pre-test service health checks, Slack alerts |
| 12 | `test_data_generator` | Faker-based test data + edge cases + blockchain fields |

## Install

```bash
pip install qaforge-mcp
playwright install chromium firefox webkit   # needed for browser/accessibility tools
```

Optionally install [k6](https://k6.io/docs/getting-started/installation/) for the performance tools.

## Register with Claude Code

```bash
claude mcp add --scope user qaforge -e ANTHROPIC_API_KEY=your-key-here -- python -m qaforge_mcp
```

This makes all 12 tools available in every Claude Code session on your machine.

### Optional integrations

Add any of these to the same `-e` flags (or a `.env` file next to your working directory) to unlock more:

| Variable | Enables |
|---|---|
| `ANTHROPIC_API_KEY` | AI-powered analysis (test generation, root-cause classification, bug reports) |
| `JIRA_URL`, `JIRA_EMAIL`, `JIRA_TOKEN`, `JIRA_PROJECT_KEY` | Auto-create Jira tickets from `bug_report_generator` |
| `SLACK_WEBHOOK` | Post test reports and environment alerts to Slack |

Tools work without any of these configured — AI-dependent tools fall back to non-AI output, and Jira/Slack features simply no-op.

## Remote connector (shared, hosted deployment)

The default setup above runs the server locally (stdio) — one process per user. To expose QAForge MCP as a **remote HTTP connector** that multiple people can add via a single URL (e.g. in Claude.ai Settings → Connectors), deploy the included `Dockerfile` (e.g. on [Render](https://render.com) using `render.yaml`, or any Docker host) and set `MCP_TRANSPORT=http`.

In this mode, the server does **not** use a shared `ANTHROPIC_API_KEY` — every caller must send their own key in the `X-Anthropic-Api-Key` request header, so nobody's usage is billed to the operator's account. Local stdio mode is unaffected and continues to use the `ANTHROPIC_API_KEY` env var as before.

```bash
docker build -t qaforge-mcp .
docker run -p 8000:8000 -e MCP_TRANSPORT=http qaforge-mcp
```

Then add it in Claude as a custom connector pointing at `https://<your-host>/mcp`, with header `X-Anthropic-Api-Key: <your-own-key>`.

**Note:** the Docker image only installs the Chromium Playwright browser to keep the image lean for free hosting tiers — `diff_browsers` will report Firefox/WebKit as failed on a hosted deployment. Run it locally (`pip install` path above) for full cross-browser diffing.

## Requirements

- Python 3.11+
- [Playwright](https://playwright.dev/) browsers for `diff_browsers`, `accessibility_checker`, `ai_test_executor`
- [k6](https://k6.io/) for `performance_baseline_mcp` and the security k6 script

## License

MIT
