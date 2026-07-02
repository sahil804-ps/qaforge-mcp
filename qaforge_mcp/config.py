import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self):
        self.anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
        self.claude_model: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

        self.jira_url: str = os.getenv("JIRA_URL", "").rstrip("/")
        self.jira_email: str = os.getenv("JIRA_EMAIL", "")
        self.jira_token: str = os.getenv("JIRA_TOKEN", "")
        self.jira_project_key: str = os.getenv("JIRA_PROJECT_KEY", "QA")

        self.slack_webhook_url: str = os.getenv("SLACK_WEBHOOK", "")

        self.baseline_file: Path = Path(os.getenv("BASELINE_FILE", "qaforge_baselines.json"))

    @property
    def jira_configured(self) -> bool:
        return bool(self.jira_url and self.jira_token)

    @property
    def slack_configured(self) -> bool:
        return bool(self.slack_webhook_url)

    @property
    def ai_configured(self) -> bool:
        return bool(self.anthropic_api_key)


config = Config()
