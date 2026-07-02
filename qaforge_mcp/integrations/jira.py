import base64
from typing import Optional
import httpx
from ..config import config


def _auth_header() -> str:
    credentials = f"{config.jira_email}:{config.jira_token}"
    return "Basic " + base64.b64encode(credentials.encode()).decode()


async def create_issue(
    summary: str,
    description: str,
    issue_type: str = "Bug",
    priority: str = "High",
    labels: Optional[list[str]] = None,
    assignee_account_id: Optional[str] = None,
) -> dict:
    if not config.jira_configured:
        return {"error": "Jira not configured. Set JIRA_URL, JIRA_EMAIL, JIRA_TOKEN env vars."}

    headers = {
        "Authorization": _auth_header(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    fields: dict = {
        "project": {"key": config.jira_project_key},
        "summary": summary,
        "description": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": description}],
                }
            ],
        },
        "issuetype": {"name": issue_type},
        "priority": {"name": priority},
    }

    if labels:
        fields["labels"] = labels
    if assignee_account_id:
        fields["assignee"] = {"accountId": assignee_account_id}

    payload = {"fields": fields}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{config.jira_url}/rest/api/3/issue",
            headers=headers,
            json=payload,
        )
        if resp.status_code == 201:
            data = resp.json()
            return {
                "key": data["key"],
                "id": data["id"],
                "url": f"{config.jira_url}/browse/{data['key']}",
            }
        return {"error": f"Jira API error {resp.status_code}: {resp.text[:500]}"}
