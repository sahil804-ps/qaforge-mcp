import json
import time
from pathlib import Path
from typing import Optional
from ..config import config
from ..integrations.k6_runner import generate_k6_script, run_k6


def _load_baselines() -> dict:
    if config.baseline_file.exists():
        try:
            return json.loads(config.baseline_file.read_text())
        except Exception:
            pass
    return {}


def _save_baselines(baselines: dict) -> None:
    config.baseline_file.write_text(json.dumps(baselines, indent=2))


def _baseline_key(endpoints: list[dict]) -> str:
    return "|".join(f"{e.get('method','GET')}:{e.get('url','')}" for e in endpoints[:5])


async def run(
    endpoints: list[dict],
    vus: int = 10,
    duration: str = "30s",
    set_as_baseline: bool = False,
) -> dict:
    if not endpoints:
        return {"error": "endpoints list required. Each item: {url, method, headers?, body?}"}

    script = generate_k6_script(endpoints, vus=vus, duration=duration)

    k6_result = await run_k6(script)

    if "error" in k6_result:
        return {
            "error": k6_result["error"],
            "k6_script": script,
            "hint": "Install k6: https://k6.io/docs/getting-started/installation/",
        }

    current_metrics = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "vus": vus,
        "duration": duration,
        "p50_ms": k6_result.get("med", 0),
        "p90_ms": k6_result.get("p90", 0),
        "p95_ms": k6_result.get("p95", 0),
        "p99_ms": k6_result.get("p99", 0),
        "avg_ms": k6_result.get("avg", 0),
        "min_ms": k6_result.get("min", 0),
        "max_ms": k6_result.get("max", 0),
        "rps": k6_result.get("rps", 0),
        "failure_rate": k6_result.get("failure_rate", 0),
        "exit_code": k6_result.get("exit_code", -1),
    }

    key = _baseline_key(endpoints)
    baselines = _load_baselines()
    existing_baseline = baselines.get(key)

    comparison: dict = {}
    alerts: list[str] = []

    if existing_baseline:
        for metric in ("p90_ms", "p95_ms", "p99_ms", "avg_ms"):
            old_val = existing_baseline.get(metric, 0)
            new_val = current_metrics.get(metric, 0)
            if old_val > 0:
                pct_change = ((new_val - old_val) / old_val) * 100
                comparison[metric] = {
                    "baseline": old_val,
                    "current": new_val,
                    "change_pct": round(pct_change, 1),
                    "status": "regression" if pct_change > 20 else "ok",
                }
                if pct_change > 20:
                    alerts.append(f"REGRESSION: {metric} increased {pct_change:.1f}% ({old_val}ms → {new_val}ms)")

    if set_as_baseline or not existing_baseline:
        baselines[key] = current_metrics
        _save_baselines(baselines)
        baseline_action = "saved as new baseline" if not existing_baseline else "updated baseline"
    else:
        baseline_action = "compared against existing baseline"

    thresholds = {
        "p90_alert_ms": (current_metrics.get("p90_ms", 0) or 0) * 1.3,
        "p95_alert_ms": (current_metrics.get("p95_ms", 0) or 0) * 1.3,
        "failure_rate_max": 0.05,
    }

    return {
        "endpoints_tested": len(endpoints),
        "load_config": {"vus": vus, "duration": duration},
        "current_metrics": current_metrics,
        "baseline_comparison": comparison,
        "alerts": alerts,
        "alert_thresholds": thresholds,
        "baseline_action": baseline_action,
        "k6_script": script,
        "passed": k6_result.get("exit_code", 1) == 0 and not alerts,
    }
