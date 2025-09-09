import os
import httpx
import asyncio
import base64
import hashlib
import urllib.parse
from typing import Dict, Any, List, Tuple

class BranchCreateError(Exception): pass
class PushError(Exception): pass

def validate_env() -> Dict[str, str]:
    """Ensure required GitHub environment variables are set."""
    cfg = {
        "GITHUB_API": os.environ.get("GITHUB_API", "https://api.github.com").rstrip("/"),
        "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", ""),
        "GITHUB_REPO": os.environ.get("GITHUB_REPO", ""),
        "GITHUB_MAIN_BRANCH": os.environ.get("GITHUB_MAIN_BRANCH", "main"),
    }
    if not all([cfg["GITHUB_TOKEN"], cfg["GITHUB_REPO"]]):
        raise RuntimeError("Missing GITHUB_TOKEN or GITHUB_REPO in environment.")
    return cfg

def validate_branch_name(name: str) -> None:
    """Basic validation to prevent path traversal or invalid branch names."""
    if not name or ".." in name or "//" in name or name.startswith("/") or name.endswith("/"):
        raise BranchCreateError(f"Invalid branch name provided: {name}")

def normalize_path(path: str) -> str:
    """Normalize path to prevent directory traversal."""
    # Collapses 'a/../b' to 'b', etc.
    normalized = os.path.normpath(path).replace("\\", "/")
    # Block absolute paths or attempts to go "up" from the root
    if os.path.isabs(normalized) or normalized.startswith(".."):
        raise PushError(f"Invalid or malicious path rejected: {path}")
    return normalized

def encode_contents_path(path: str) -> str:
    """URL-encode path segments for the GitHub contents API."""
    return "/".join(urllib.parse.quote(part) for part in path.split("/"))

def sanitize_commit_message(msg: str) -> str:
    """Strip control chars, collapse lines, trim length, and ensure non-empty."""
    if not isinstance(msg, str):
        return "update via integrator"
    cleaned = "".join(ch if (ch == "\n" or 32 <= ord(ch) <= 126) else " " for ch in msg)
    cleaned = cleaned.replace("\r", "").strip()
    if "\n" in cleaned:
        head, *rest = cleaned.splitlines()
        cleaned = head[:200].rstrip() + ("" if not rest else " · " + " ".join(s.strip() for s in rest)[:200])
    if len(cleaned) > 256:
        cleaned = cleaned[:256].rstrip() + "…"
    return cleaned or "update via integrator"

async def _request_with_retries(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_retries: int = 2,
    backoff_start: float = 0.5,
    **kwargs,
) -> httpx.Response:
    """Attempt a request with retries on network errors and 5xx responses."""
    backoff = backoff_start
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            resp = await client.request(method, url, **kwargs)
            if 500 <= resp.status_code < 600 and attempt < max_retries:
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
            return resp
        except httpx.RequestError as e:
            last_exc = e
            if attempt < max_retries:
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
    raise PushError(f"Network error talking to GitHub: {last_exc!s}") from last_exc

async def create_branch(cfg: Dict[str, str], branch: str) -> bool:
    """Create a new branch from the main branch. Returns False if it already exists."""
    validate_branch_name(branch)
    api_base = cfg["GITHUB_API"]
    headers = {"Authorization": f"token {cfg['GITHUB_TOKEN']}", "Accept": "application/vnd.github.v3+json"}

    async with httpx.AsyncClient(headers=headers, timeout=20.0) as client:
        # 1. Get the SHA of the main branch
        main_branch_url = f"{api_base}/repos/{cfg['GITHUB_REPO']}/git/ref/heads/{cfg['GITHUB_MAIN_BRANCH']}"
        resp = await _request_with_retries(client, "GET", main_branch_url)
        if resp.status_code != 200:
            raise BranchCreateError(f"Could not find main branch '{cfg['GITHUB_MAIN_BRANCH']}'. Status: {resp.status_code}")
        main_sha = resp.json()["object"]["sha"]

        # 2. Try to create the new branch
        create_ref_url = f"{api_base}/repos/{cfg['GITHUB_REPO']}/git/refs"
        payload = {"ref": f"refs/heads/{branch}", "sha": main_sha}
        resp = await _request_with_retries(client, "POST", create_ref_url, json=payload)

        if resp.status_code == 201:
            return True  # Success
        if resp.status_code == 422 and "Reference already exists" in resp.text:
            return False # Branch already exists
        
        raise BranchCreateError(f"Failed to create branch. Status: {resp.status_code}, Response: {resp.text}")

async def put_file(
    client: httpx.AsyncClient,
    cfg: Dict[str, str],
    branch: str,
    path: str,
    content: bytes,
    commit_msg: str,
) -> bool:
    """Create or update a single file in the repo. Skips if content is identical. Returns True if written."""
    api_base = cfg["GITHUB_API"]
    encoded_path = encode_contents_path(path)
    url = f"{api_base}/repos/{cfg['GITHUB_REPO']}/contents/{encoded_path}"
    
    # Check if the file exists and get its SHA
    resp = await _request_with_retries(client, "GET", url, params={"ref": branch})
    sha = None
    if resp.status_code == 200:
        existing_content = base64.b64decode(resp.json()["content"])
        if existing_content == content:
            return False  # Content is identical, skip.
        sha = resp.json()["sha"]

    # Create or update the file
    payload = {
        "message": commit_msg,
        "content": base64.b64encode(content).decode(),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    
    resp = await _request_with_retries(client, "PUT", url, json=payload)
    if resp.status_code not in (200, 201):
        raise PushError(f"GitHub API error writing '{path}': {resp.status_code} {resp.text}")
    return True

async def push_files(
    cfg: Dict[str, str], branch: str, files: List[Tuple[str, bytes]], commit_title: str
) -> Dict[str, int]:
    """Pushes a list of files to the specified branch."""
    validate_branch_name(branch)
    headers = {"Authorization": f"token {cfg['GITHUB_TOKEN']}", "Accept": "application/vnd.github.v3+json"}
    commit_msg = sanitize_commit_message(commit_title)
    written, skipped = 0, 0

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        for path, content in files:
            try:
                norm_path = normalize_path(path)
                was_written = await put_file(client, cfg, branch, norm_path, content, commit_msg)
                if was_written:
                    written += 1
                else:
                    skipped += 1
            except PushError as e:
                # Re-raise to be caught by the API endpoint
                raise e
            except Exception as e:
                raise PushError(f"An unexpected error occurred processing '{path}': {e}")

    return {"written": written, "skipped": skipped}