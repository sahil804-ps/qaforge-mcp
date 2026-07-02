import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

_K6_CANDIDATES = [
    "k6",
    r"C:\Program Files\k6\k6.exe",
    r"C:\Program Files (x86)\k6\k6.exe",
    str(Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages" / "GrafanaLabs.k6_Microsoft.Winget.Source_8wekyb3d8bbwe" / "k6.exe"),
]


def _find_k6() -> str:
    if found := shutil.which("k6"):
        return found
    for candidate in _K6_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return "k6"


def generate_k6_script(
    endpoints: list[dict],
    vus: int = 10,
    duration: str = "30s",
    baseline_thresholds: Optional[dict] = None,
) -> str:
    endpoint_calls = []
    for ep in endpoints:
        method = ep.get("method", "GET").upper()
        url = ep.get("url", "")
        headers = ep.get("headers", {})
        body = ep.get("body", None)

        url_js = json.dumps(url)
        headers_js = json.dumps(headers)
        if method == "GET":
            endpoint_calls.append(f'    http.get({url_js}, {{headers: {headers_js}}});')
        else:
            body_js = json.dumps(body) if body else "null"
            endpoint_calls.append(
                f'    http.{method.lower()}({url_js}, JSON.stringify({body_js}), {{headers: {headers_js}}});'
            )

    calls_block = "\n".join(endpoint_calls) if endpoint_calls else '    http.get(__ENV.TARGET_URL || "http://localhost:3000");'

    thresholds = baseline_thresholds or {
        "http_req_duration": ["p(90)<2000", "p(95)<3000"],
        "http_req_failed": ["rate<0.05"],
    }
    thresholds_js = json.dumps(thresholds, indent=4)

    return f"""import http from 'k6/http';
import {{ check, sleep }} from 'k6';

export const options = {{
    vus: {vus},
    duration: '{duration}',
    thresholds: {thresholds_js},
}};

export default function () {{
{calls_block}
    sleep(1);
}}
"""


async def run_k6(script_content: str, output_json: bool = True) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = Path(tmpdir) / "test.js"
        output_path = Path(tmpdir) / "results.json"
        script_path.write_text(script_content)

        cmd = [_find_k6(), "run"]
        if output_json:
            cmd += ["--out", f"json={output_path}"]
        cmd.append(str(script_path))

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=tmpdir,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        except FileNotFoundError:
            return {"error": "k6 not installed. Install from https://k6.io/docs/getting-started/installation/"}
        except asyncio.TimeoutError:
            proc.kill()
            return {"error": "k6 run timed out after 5 minutes"}

        stdout_text = stdout.decode(errors="replace")
        stderr_text = stderr.decode(errors="replace")

        metrics = _parse_k6_stdout(stdout_text)
        metrics["exit_code"] = proc.returncode
        metrics["stdout"] = stdout_text[-3000:]
        if proc.returncode != 0:
            metrics["stderr"] = stderr_text[-1000:]

        return metrics


def _parse_k6_stdout(output: str) -> dict:
    metrics: dict = {}
    for line in output.splitlines():
        if "http_req_duration" in line and "avg=" in line:
            metrics["raw_duration_line"] = line.strip()
            for part in line.split():
                for key in ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"]:
                    if part.startswith(key + "="):
                        val_str = part.split("=")[1].replace("ms", "").replace("s", "")
                        try:
                            metrics[key.replace("(", "").replace(")", "")] = float(val_str)
                        except ValueError:
                            pass
        elif "http_req_failed" in line and "rate=" in line:
            for part in line.split():
                if part.startswith("rate="):
                    try:
                        metrics["failure_rate"] = float(part.split("=")[1].rstrip("%")) / 100
                    except ValueError:
                        pass
        elif "http_reqs" in line and "rate=" in line:
            for part in line.split():
                if part.startswith("rate="):
                    try:
                        metrics["rps"] = float(part.split("=")[1].split("/")[0])
                    except ValueError:
                        pass
    return metrics
