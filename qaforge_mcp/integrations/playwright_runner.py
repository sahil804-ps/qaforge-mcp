import asyncio
import base64
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page


async def get_page_snapshot(url: str, browser_type: str = "chromium") -> dict:
    async with async_playwright() as p:
        launcher = getattr(p, browser_type)
        browser: Browser = await launcher.launch(headless=True)
        context: BrowserContext = await browser.new_context()
        page: Page = await context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            title = await page.title()
            screenshot_bytes = await page.screenshot(full_page=True)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
            dom_snapshot = await page.evaluate("document.documentElement.outerHTML")
            perf = await page.evaluate("""() => {
                const nav = performance.getEntriesByType('navigation')[0];
                return nav ? {
                    dom_content_loaded: Math.round(nav.domContentLoadedEventEnd),
                    load: Math.round(nav.loadEventEnd)
                } : {};
            }""")
            return {
                "browser": browser_type,
                "url": url,
                "title": title,
                "screenshot_b64": screenshot_b64,
                "dom_length": len(dom_snapshot),
                "dom_snippet": dom_snapshot[:2000],
                "js_errors": errors,
                "performance_ms": perf,
            }
        except Exception as e:
            return {"browser": browser_type, "url": url, "error": str(e)}
        finally:
            await browser.close()


async def run_axe_audit(url: str) -> dict:
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=True)
        page: Page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.add_script_tag(url="https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js")
            await page.wait_for_function("typeof axe !== 'undefined'", timeout=10000)
            results = await page.evaluate("""async () => {
                const result = await axe.run();
                return {
                    violations: result.violations,
                    passes: result.passes.length,
                    incomplete: result.incomplete.length,
                    inapplicable: result.inapplicable.length
                };
            }""")
            return results
        except Exception as e:
            return {"error": str(e), "violations": []}
        finally:
            await browser.close()


async def execute_steps(url: str, steps: list[str]) -> dict:
    """Execute a list of natural-language-like Playwright steps on a URL."""
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=True)
        page: Page = await browser.new_page()
        executed: list[dict] = []
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            for step in steps:
                step_lower = step.lower().strip()
                try:
                    if step_lower.startswith("click "):
                        selector = step[6:].strip().strip("'\"")
                        await page.click(selector, timeout=10000)
                        executed.append({"step": step, "status": "pass"})
                    elif step_lower.startswith("fill "):
                        parts = step[5:].split(" with ", 1)
                        if len(parts) == 2:
                            selector = parts[0].strip().strip("'\"")
                            value = parts[1].strip().strip("'\"")
                            await page.fill(selector, value, timeout=10000)
                            executed.append({"step": step, "status": "pass"})
                    elif step_lower.startswith("assert visible "):
                        selector = step[15:].strip().strip("'\"")
                        await page.wait_for_selector(selector, state="visible", timeout=10000)
                        executed.append({"step": step, "status": "pass"})
                    elif step_lower.startswith("assert text "):
                        text = step[12:].strip().strip("'\"")
                        await page.wait_for_function(
                            f"document.body.innerText.includes({repr(text)})", timeout=10000
                        )
                        executed.append({"step": step, "status": "pass"})
                    elif step_lower.startswith("navigate "):
                        nav_url = step[9:].strip()
                        await page.goto(nav_url, wait_until="networkidle", timeout=30000)
                        executed.append({"step": step, "status": "pass"})
                    else:
                        executed.append({"step": step, "status": "skipped", "reason": "unrecognized step"})
                except Exception as e:
                    executed.append({"step": step, "status": "fail", "error": str(e)})
            final_url = page.url
            return {"steps": executed, "final_url": final_url}
        except Exception as e:
            return {"steps": executed, "error": str(e)}
        finally:
            await browser.close()
