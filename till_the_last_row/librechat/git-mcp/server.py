#!/usr/bin/env python3
"""
Atlys git-write MCP server.

A tiny HTTP MCP server that lets the Instrumentation Agent commit a generated
ClickHouse schema file and push it DIRECTLY to the target branch (default `master`)
of the target repo — no feature branch, no PR — without needing a local shell.

It manages its own clone under $CH_REPO_DIR and authenticates to GitHub over HTTPS
using a Personal Access Token ($GITHUB_TOKEN) injected into the remote URL.

Tools:
  - repo_status()                       -> current branch, HEAD sha, dirty files
  - list_schemas()                      -> existing files under Atlys/schemas/
  - write_and_push(relative_path, content, message)
                                        -> write file, commit, push to target branch,
                                           return commit sha + URL

Config (env):
  GITHUB_TOKEN        (required)  GitHub PAT with `repo` scope
  CH_TARGET_REPO      repo URL              (default: https://github.com/srinidhi-22/tillthelastrow.git)
  CH_TARGET_BRANCH    branch to push to     (default: master)
  CH_REPO_DIR         local clone dir       (default: /work/<repo-name>)
  GIT_AUTHOR_NAME     commit author name    (default: Atlys Instrumentation Agent)
  GIT_AUTHOR_EMAIL    commit author email   (default: atlys-agent@users.noreply.github.com)
  MCP_BIND_HOST       (default: 0.0.0.0)
  MCP_BIND_PORT       (default: 8000)
"""
import os
import re
import subprocess
from pathlib import Path

from fastmcp import FastMCP

TARGET_REPO = os.environ.get(
    "CH_TARGET_REPO", "https://github.com/srinidhi-22/tillthelastrow.git"
)
TARGET_BRANCH = os.environ.get("CH_TARGET_BRANCH", "master")
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
AUTHOR_NAME = os.environ.get("GIT_AUTHOR_NAME", "Atlys Instrumentation Agent")
AUTHOR_EMAIL = os.environ.get(
    "GIT_AUTHOR_EMAIL", "atlys-agent@users.noreply.github.com"
)

_repo_name = re.sub(r"\.git$", "", TARGET_REPO.rstrip("/").split("/")[-1])
REPO_DIR = Path(os.environ.get("CH_REPO_DIR", f"/work/{_repo_name}"))

mcp = FastMCP("atlys-git-write")


def _host_and_slug(url: str):
    """Return (host, 'owner/repo') from an https or ssh git URL."""
    m = re.match(r"^[a-z]+://([^/]+)/(.+?)(?:\.git)?/?$", url)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^git@([^:]+):(.+?)(?:\.git)?/?$", url)
    if m:
        return m.group(1), m.group(2)
    return "github.com", url


HOST, SLUG = _host_and_slug(TARGET_REPO)


def _authed_url() -> str:
    """https URL with the PAT embedded for push/pull auth."""
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is not set — cannot authenticate to GitHub.")
    return f"https://x-access-token:{TOKEN}@{HOST}/{SLUG}.git"


def _run(args, cwd=None, check=True):
    """Run a git/subprocess command; never echo the token in output."""
    proc = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    if TOKEN:
        out = out.replace(TOKEN, "***")
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed ({' '.join(args[:2])}...): {out.strip()}")
    return out.strip()


def _ensure_clone():
    """Clone once, then fetch + hard-reset to the latest target branch tip."""
    if not (REPO_DIR / ".git").is_dir():
        REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "clone", _authed_url(), str(REPO_DIR)])
    # keep remote authenticated (token may rotate) and refresh
    _run(["git", "remote", "set-url", "origin", _authed_url()], cwd=REPO_DIR)
    _run(["git", "config", "user.name", AUTHOR_NAME], cwd=REPO_DIR)
    _run(["git", "config", "user.email", AUTHOR_EMAIL], cwd=REPO_DIR)
    _run(["git", "fetch", "origin", "--prune"], cwd=REPO_DIR)
    _run(["git", "checkout", TARGET_BRANCH], cwd=REPO_DIR)
    _run(["git", "reset", "--hard", f"origin/{TARGET_BRANCH}"], cwd=REPO_DIR)


@mcp.tool()
def repo_status() -> dict:
    """Refresh the clone and report the target repo/branch, HEAD sha, and any dirty files."""
    _ensure_clone()
    head = _run(["git", "rev-parse", "HEAD"], cwd=REPO_DIR)
    dirty = _run(["git", "status", "--porcelain"], cwd=REPO_DIR, check=False)
    return {
        "repo": f"{HOST}/{SLUG}",
        "branch": TARGET_BRANCH,
        "head": head,
        "dirty_files": dirty.splitlines() if dirty else [],
    }


@mcp.tool()
def list_schemas() -> dict:
    """List existing files under Atlys/schemas/ so the agent can check for name collisions."""
    _ensure_clone()
    schemas_dir = REPO_DIR / "Atlys" / "schemas"
    files = (
        sorted(p.name for p in schemas_dir.glob("*") if p.is_file())
        if schemas_dir.is_dir()
        else []
    )
    return {"dir": "Atlys/schemas", "files": files}


@mcp.tool()
def write_and_push(relative_path: str, content: str, message: str) -> dict:
    """
    Write `content` to `relative_path` in the repo, commit it on the target branch,
    and push DIRECTLY to that branch (no feature branch, no PR). Returns the commit
    sha and URL.

    Args:
        relative_path: path inside the repo, e.g. 'Atlys/schemas/01_express_checkout.sql'.
                       Must stay within the repo; '..' is rejected.
        content:       full file contents to write (overwrites if it exists).
        message:       commit message.
    """
    _ensure_clone()

    rel = relative_path.lstrip("/")
    target = (REPO_DIR / rel).resolve()
    if not str(target).startswith(str(REPO_DIR.resolve()) + os.sep):
        raise RuntimeError(f"relative_path escapes the repo: {relative_path!r}")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)

    _run(["git", "add", rel], cwd=REPO_DIR)

    # nothing staged => no-op (idempotent re-run with identical content)
    staged = _run(["git", "diff", "--cached", "--name-only"], cwd=REPO_DIR, check=False)
    if not staged:
        head = _run(["git", "rev-parse", "HEAD"], cwd=REPO_DIR)
        return {
            "committed": False,
            "reason": "no changes (file content identical to HEAD)",
            "path": rel,
            "branch": TARGET_BRANCH,
            "commit": head,
            "commit_url": f"https://{HOST}/{SLUG}/commit/{head}",
        }

    _run(["git", "commit", "-m", message], cwd=REPO_DIR)

    # push directly; if remote advanced, rebase our single commit and retry once
    try:
        push_out = _run(["git", "push", "origin", f"HEAD:{TARGET_BRANCH}"], cwd=REPO_DIR)
    except RuntimeError:
        _run(["git", "pull", "--rebase", "origin", TARGET_BRANCH], cwd=REPO_DIR)
        push_out = _run(["git", "push", "origin", f"HEAD:{TARGET_BRANCH}"], cwd=REPO_DIR)

    sha = _run(["git", "rev-parse", "HEAD"], cwd=REPO_DIR)
    return {
        "committed": True,
        "pushed": True,
        "path": rel,
        "branch": TARGET_BRANCH,
        "commit": sha,
        "commit_url": f"https://{HOST}/{SLUG}/commit/{sha}",
        "message": message,
        "push_output": push_out,
    }


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=os.environ.get("MCP_BIND_HOST", "0.0.0.0"),
        port=int(os.environ.get("MCP_BIND_PORT", "8000")),
    )
