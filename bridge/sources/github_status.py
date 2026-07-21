"""Optional GitHub workbench status using read-only REST API calls."""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any

from schema import GithubStatus

TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or None
REPOSITORIES = [item.strip() for item in os.environ.get("RLCD_GITHUB_REPOS", "").split(",")
                if item.strip()]
TTL = int(os.environ.get("RLCD_GITHUB_TTL", "300"))
_cache: dict[str, object] = {"value": None, "ts": 0.0}


def _get(path: str) -> dict[str, Any]:
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "User-Agent": "codex-token-monitor-rlcd",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.load(response)


def _review_requests(login: str) -> int:
    qualifiers = " ".join(f"repo:{repository}" for repository in REPOSITORIES)
    query = urllib.parse.quote(f"is:pr is:open review-requested:{login} {qualifiers}")
    return int(_get(f"/search/issues?q={query}&per_page=1").get("total_count") or 0)


def _failing_workflows(repository: str) -> int:
    repo = _get(f"/repos/{repository}")
    branch = urllib.parse.quote(str(repo.get("default_branch") or "main"), safe="")
    runs = _get(f"/repos/{repository}/actions/runs?branch={branch}&status=completed&per_page=100")
    latest_by_workflow: dict[int, str] = {}
    for run in runs.get("workflow_runs") or []:
        workflow_id = int(run.get("workflow_id") or 0)
        if workflow_id and workflow_id not in latest_by_workflow:
            latest_by_workflow[workflow_id] = str(run.get("conclusion") or "")
    failed = {"failure", "timed_out", "action_required", "startup_failure"}
    return sum(conclusion in failed for conclusion in latest_by_workflow.values())


def fetch_github_status() -> GithubStatus | None:
    if not TOKEN or not REPOSITORIES:
        return None
    now = time.time()
    if _cache["value"] is not None and now - float(_cache["ts"]) < TTL:
        return _cache["value"]  # type: ignore[return-value]
    try:
        login = str(_get("/user").get("login") or "")
        value = GithubStatus(
            review_requests=_review_requests(login) if login else 0,
            failing_workflows=sum(_failing_workflows(repo) for repo in REPOSITORIES),
            repositories=len(REPOSITORIES),
            valid=True,
        )
        _cache.update(value=value, ts=now)
        return value
    except Exception:
        return _cache["value"]  # type: ignore[return-value]
