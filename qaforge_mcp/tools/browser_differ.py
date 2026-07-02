import asyncio
from ..integrations.playwright_runner import get_page_snapshot


async def run(url: str, scenario_description: str = "") -> dict:
    browsers = ["chromium", "firefox", "webkit"]

    snapshots = await asyncio.gather(
        *[get_page_snapshot(url, b) for b in browsers],
        return_exceptions=True,
    )

    results: dict[str, dict] = {}
    for browser, snapshot in zip(browsers, snapshots):
        if isinstance(snapshot, Exception):
            results[browser] = {"error": str(snapshot)}
        else:
            results[browser] = snapshot

    diffs = _compute_diffs(results)

    severity = "pass"
    if any(d["severity"] == "critical" for d in diffs):
        severity = "critical"
    elif any(d["severity"] == "warning" for d in diffs):
        severity = "warning"

    return {
        "url": url,
        "scenario": scenario_description,
        "browsers_tested": browsers,
        "overall_severity": severity,
        "diffs": diffs,
        "summary": _summarize(results, diffs),
        "browser_results": {b: {k: v for k, v in s.items() if k not in ("screenshot_b64", "dom_snippet")} for b, s in results.items()},
    }


def _compute_diffs(results: dict[str, dict]) -> list[dict]:
    diffs = []
    browsers = list(results.keys())

    titles = {b: results[b].get("title", "") for b in browsers if "error" not in results[b]}
    unique_titles = set(titles.values())
    if len(unique_titles) > 1:
        diffs.append({
            "type": "title_mismatch",
            "severity": "warning",
            "detail": f"Different page titles: {titles}",
        })

    dom_lengths = {b: results[b].get("dom_length", 0) for b in browsers if "error" not in results[b]}
    if dom_lengths:
        max_len = max(dom_lengths.values())
        min_len = min(dom_lengths.values())
        if max_len > 0 and (max_len - min_len) / max_len > 0.15:
            diffs.append({
                "type": "dom_size_variance",
                "severity": "warning",
                "detail": f"DOM size differs significantly across browsers: {dom_lengths}",
            })

    for browser, data in results.items():
        if "error" in data:
            diffs.append({
                "type": "browser_error",
                "severity": "critical",
                "browser": browser,
                "detail": f"{browser} failed to load: {data['error']}",
            })
        elif data.get("js_errors"):
            diffs.append({
                "type": "js_errors",
                "severity": "warning",
                "browser": browser,
                "detail": f"{browser} JS errors: {data['js_errors'][:3]}",
            })

    perf_data = {b: results[b].get("performance_ms", {}) for b in browsers if "error" not in results[b]}
    for browser, perf in perf_data.items():
        if perf.get("load", 0) > 5000:
            diffs.append({
                "type": "slow_load",
                "severity": "warning",
                "browser": browser,
                "detail": f"{browser} load time {perf['load']}ms exceeds 5s threshold",
            })

    return diffs


def _summarize(results: dict, diffs: list) -> str:
    working = [b for b, r in results.items() if "error" not in r]
    broken = [b for b, r in results.items() if "error" in r]
    lines = [f"Tested on {len(results)} browsers. Working: {', '.join(working) or 'none'}."]
    if broken:
        lines.append(f"Failed: {', '.join(broken)}.")
    if diffs:
        critical = sum(1 for d in diffs if d["severity"] == "critical")
        warnings = sum(1 for d in diffs if d["severity"] == "warning")
        lines.append(f"Found {critical} critical issues and {warnings} warnings.")
    else:
        lines.append("No cross-browser differences detected.")
    return " ".join(lines)
