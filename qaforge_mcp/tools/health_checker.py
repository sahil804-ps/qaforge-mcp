import asyncio
import time
from typing import Optional
import httpx
from ..integrations import slack as slack_client
from ..config import config


async def _check_service(name: str, url: str, timeout: float = 10.0) -> dict:
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
        elapsed_ms = round((time.monotonic() - start) * 1000)

        if resp.status_code < 400:
            status = "UP"
        elif resp.status_code < 500:
            status = "DEGRADED"
        else:
            status = "DOWN"

        return {
            "service": name,
            "url": url,
            "status": status,
            "http_status": resp.status_code,
            "response_time_ms": elapsed_ms,
            "slow": elapsed_ms > 2000,
        }
    except httpx.TimeoutException:
        return {
            "service": name,
            "url": url,
            "status": "DOWN",
            "error": "timeout",
            "response_time_ms": round(timeout * 1000),
        }
    except httpx.ConnectError as e:
        return {
            "service": name,
            "url": url,
            "status": "DOWN",
            "error": f"connection refused: {str(e)[:100]}",
            "response_time_ms": round((time.monotonic() - start) * 1000),
        }
    except Exception as e:
        return {
            "service": name,
            "url": url,
            "status": "DOWN",
            "error": str(e)[:200],
            "response_time_ms": round((time.monotonic() - start) * 1000),
        }


async def run(
    service_urls: dict[str, str],
    alert_on_failure: bool = False,
    timeout_seconds: float = 10.0,
) -> dict:
    if not service_urls:
        return {"error": "service_urls dict required. Example: {'API': 'http://api.example.com/health', 'DB': 'http://db-health.internal'}"}

    tasks = [_check_service(name, url, timeout_seconds) for name, url in service_urls.items()]
    results = await asyncio.gather(*tasks)

    services = list(results)
    up = [s for s in services if s["status"] == "UP"]
    down = [s for s in services if s["status"] == "DOWN"]
    degraded = [s for s in services if s["status"] == "DEGRADED"]
    slow = [s for s in services if s.get("slow")]

    overall = "HEALTHY"
    if down:
        overall = "CRITICAL"
    elif degraded or slow:
        overall = "DEGRADED"

    summary = {
        "overall_status": overall,
        "total": len(services),
        "up": len(up),
        "down": len(down),
        "degraded": len(degraded),
        "slow_responses": len(slow),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    result = {
        "summary": summary,
        "services": services,
        "down_services": [s["service"] for s in down],
        "degraded_services": [s["service"] for s in degraded],
        "recommendation": _get_recommendation(overall, down, degraded, slow),
        "safe_to_run_tests": overall == "HEALTHY",
    }

    if alert_on_failure and down and config.slack_configured:
        alert_text = f"ENVIRONMENT ALERT: {len(down)} service(s) DOWN — {', '.join(s['service'] for s in down)}. Test run blocked."
        slack_result = await slack_client.send_message(alert_text)
        result["slack_alert"] = slack_result

    return result


def _get_recommendation(overall: str, down: list, degraded: list, slow: list) -> str:
    if overall == "HEALTHY":
        return "Environment is healthy. Safe to run test suite."
    if down:
        services = ", ".join(s["service"] for s in down)
        return f"BLOCK test run. {len(down)} service(s) are DOWN: {services}. Fix infrastructure before testing."
    if degraded:
        services = ", ".join(s["service"] for s in degraded)
        return f"Run tests with caution. {len(degraded)} service(s) DEGRADED: {services}. Results may be unreliable."
    if slow:
        services = ", ".join(s["service"] for s in slow)
        return f"Services responding slowly: {services}. Performance tests will show inflated numbers."
    return "Environment status unclear."
