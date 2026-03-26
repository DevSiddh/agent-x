"""
phase3/project_manager.py
Project lifecycle: create GitHub repo, delete project, list projects.
No cross-imports from phase1/ or phase2/.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import requests
import structlog

log = structlog.get_logger()
_REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = _REPO_ROOT / "memory" / "registry.jsonl"


# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------

def _gh_token() -> str:
    return os.environ.get("GITHUB_TOKEN", "")


def _gh_owner() -> str:
    return os.environ.get("GITHUB_USERNAME", "")


def _gh_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_gh_token()}", "Accept": "application/vnd.github+json"}


def create_github_repo(project_slug: str) -> str | None:
    """Create a GitHub repo for the project. Returns clone URL or None on failure."""
    token = _gh_token()
    owner = _gh_owner()
    if not token or not owner:
        log.warning("project_manager.github_skip", reason="GITHUB_TOKEN or GITHUB_USERNAME not set")
        return None
    try:
        resp = requests.post(
            "https://api.github.com/user/repos",
            headers=_gh_headers(),
            json={"name": project_slug, "private": False, "auto_init": False},
            timeout=15,
        )
        if resp.status_code in (201, 422):  # 422 = already exists
            clone_url = f"https://github.com/{owner}/{project_slug}.git"
            log.info("project_manager.github_repo_ready", url=clone_url)
            return clone_url
        log.warning("project_manager.github_create_failed", status=resp.status_code)
        return None
    except Exception as exc:
        log.warning("project_manager.github_error", error=str(exc))
        return None


def add_github_remote(repo_path: Path, clone_url: str) -> bool:
    """Add origin remote if not already set. Returns True on success."""
    try:
        existing = subprocess.run(
            ["git", "remote"], cwd=repo_path, capture_output=True, text=True
        )
        if "origin" in existing.stdout:
            return True
        subprocess.run(
            ["git", "remote", "add", "origin", clone_url],
            cwd=repo_path, check=True, capture_output=True,
        )
        log.info("project_manager.remote_added", url=clone_url)
        return True
    except Exception as exc:
        log.warning("project_manager.remote_error", error=str(exc))
        return False


def setup_github(project_slug: str, repo_path: Path) -> None:
    """Create GitHub repo + wire remote. Call once at project start."""
    clone_url = create_github_repo(project_slug)
    if clone_url:
        add_github_remote(repo_path, clone_url)


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def list_projects() -> list[dict]:
    """Return all registry entries sorted by created_at desc."""
    if not REGISTRY_PATH.exists():
        return []
    entries = []
    for line in REGISTRY_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return sorted(entries, key=lambda e: e.get("created_at", ""), reverse=True)


def _remove_from_registry(project_slug: str) -> None:
    if not REGISTRY_PATH.exists():
        return
    lines = [
        line for line in REGISTRY_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("project_slug") != project_slug
    ]
    REGISTRY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def delete_project(project_slug: str, archive_github: bool = True) -> str:
    """
    Delete a project from VPS disk + registry.
    GitHub repo: archive by default (safe), delete only if archive_github=False.
    Returns a status message.
    """
    workspace = Path(os.environ.get("WORKSPACE_ROOT", str(_REPO_ROOT / "projects")))
    project_path = workspace / project_slug

    # 1. Remove from VPS disk
    if project_path.exists():
        shutil.rmtree(project_path)
        log.info("project_manager.deleted_local", path=str(project_path))

    # 2. Remove from registry
    _remove_from_registry(project_slug)
    log.info("project_manager.registry_removed", slug=project_slug)

    # 3. Archive or delete GitHub repo
    token = _gh_token()
    owner = _gh_owner()
    github_msg = ""
    if token and owner:
        if archive_github:
            resp = requests.patch(
                f"https://api.github.com/repos/{owner}/{project_slug}",
                headers=_gh_headers(),
                json={"archived": True},
                timeout=15,
            )
            github_msg = "GitHub repo archived." if resp.status_code == 200 else "GitHub archive failed."
        else:
            resp = requests.delete(
                f"https://api.github.com/repos/{owner}/{project_slug}",
                headers=_gh_headers(),
                timeout=15,
            )
            github_msg = "GitHub repo deleted." if resp.status_code == 204 else "GitHub delete failed."

    return f"✅ {project_slug} deleted from VPS. {github_msg}".strip()
