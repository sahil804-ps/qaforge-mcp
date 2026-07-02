from typing import Optional
import httpx
from ..config import config


async def send_message(text: str, blocks: Optional[list] = None) -> dict:
    if not config.slack_configured:
        return {"error": "Slack not configured. Set SLACK_WEBHOOK env var."}

    payload: dict = {"text": text}
    if blocks:
        payload["blocks"] = blocks

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(config.slack_webhook_url, json=payload)
        if resp.status_code == 200:
            return {"status": "sent"}
        return {"error": f"Slack error {resp.status_code}: {resp.text}"}


async def send_qa_report(summary: str, pass_count: int, fail_count: int, channel_note: str = "") -> dict:
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "QAForge Test Report"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Passed:* {pass_count}"},
                {"type": "mrkdwn", "text": f"*Failed:* {fail_count}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": summary},
        },
    ]
    if channel_note:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": channel_note}]})

    return await send_message(text=f"QA Report: {pass_count} passed, {fail_count} failed", blocks=blocks)

