#!/usr/bin/env python3
"""Propose at most one non-mechanical library/feature improvement.

Weekly GitHub job. No-ops without an LLM API key. Skips if an open issue
already has the weekly-library-improvement label (the cap).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

LABEL = "weekly-library-improvement"
REPO_DEFAULT = "calmmage/botspot"


def already_has_open_suggestion(issues: list[dict[str, Any]]) -> bool:
    """True when any open issue already carries the weekly-improvement label."""
    for issue in issues:
        labels = issue.get("labels") or []
        names = [label.get("name") if isinstance(label, dict) else str(label) for label in labels]
        if LABEL in names:
            return True
    return False


def llm_api_key() -> str | None:
    for name in ("XAI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def github_repo() -> str:
    return os.environ.get("GITHUB_REPOSITORY", REPO_DEFAULT)


def github_token() -> str | None:
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def list_open_improvement_issues(token: str, repo: str) -> list[dict[str, Any]]:
    url = f"https://api.github.com/repos/{repo}/issues?state=open&labels={LABEL}&per_page=5"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "botspot-deps-suggest",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    return payload if isinstance(payload, list) else []


def create_issue(token: str, repo: str, title: str, body: str) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{repo}/issues"
    data = json.dumps({"title": title, "body": body, "labels": [LABEL]}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "botspot-deps-suggest",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def build_prompt(pyproject_text: str) -> str:
    return (
        "Propose exactly ONE non-mechanical library or feature improvement for this "
        "Python Telegram bot framework. Not a version bump, not a lockfile refresh, "
        "not a security patch. Reply as JSON with keys title and body.\n\n"
        f"{pyproject_text[:4000]}"
    )


def request_suggestion(api_key: str, prompt: str) -> tuple[str, str]:
    """Call xAI if the key looks like ours; otherwise skip generation."""
    if os.environ.get("XAI_API_KEY", "").strip() == api_key:
        payload = {
            "model": os.environ.get("XAI_MODEL", "grok-4-fast"),
            "messages": [
                {
                    "role": "system",
                    "content": "You suggest one concrete library/feature improvement.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        req = urllib.request.Request(
            "https://api.x.ai/v1/chat/completions",
            data=json.dumps(payload).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "botspot-deps-suggest",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
        content = data["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
            return str(parsed["title"]), str(parsed["body"])
        except (json.JSONDecodeError, KeyError, TypeError):
            return "Weekly library improvement", content
    raise RuntimeError("unsupported LLM provider for this key")


def run(
    *,
    issues: list[dict[str, Any]] | None = None,
    api_key: str | None = None,
    token: str | None = None,
    create=create_issue,
    suggest=request_suggestion,
    repo: str | None = None,
    pyproject_text: str | None = None,
) -> int:
    """Return 0 always for the workflow; create at most one issue."""
    key = api_key if api_key is not None else llm_api_key()
    if not key:
        print("skip: no LLM API key (XAI_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY)")
        return 0

    gh_token = token if token is not None else github_token()
    if not gh_token:
        print("skip: no GITHUB_TOKEN")
        return 0

    repo_name = repo or github_repo()
    open_issues = issues if issues is not None else list_open_improvement_issues(gh_token, repo_name)
    if already_has_open_suggestion(open_issues):
        print("skip: an open weekly-library-improvement issue already exists")
        return 0

    if pyproject_text is None:
        pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        pyproject_text = pyproject_path.read_text(encoding="utf-8")

    title, body = suggest(key, build_prompt(pyproject_text))
    issue = create(gh_token, repo_name, title, body)
    print(f"created: {issue.get('html_url', title)}")
    return 0


def main() -> int:
    try:
        return run()
    except urllib.error.HTTPError as exc:
        print(f"github/llm http error: {exc.code} {exc.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"network error: {exc.reason}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
