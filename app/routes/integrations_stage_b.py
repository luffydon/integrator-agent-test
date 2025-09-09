from __future__ import annotations

import os
import re
import httpx
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/integrations/stage-b", tags=["integrations-stage-b"])

# --------- Config / env ---------
def _need(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v

def validate_env() -> Dict[str, str]:
    api = os.environ.get("GITHUB_API", "https://api.github.com").rstrip("/")
    token = _need("GITHUB_TOKEN")
    repo = _need("GITHUB_REPO")
    base = os.environ.get("GITHUB_BASE", "main")
    if repo.count("/") != 1:
        raise RuntimeError("GITHUB_REPO must look like 'owner/repo'")
    return {"GITHUB_API": api, "GITHUB_TOKEN": token, "GITHUB_REPO": repo, "GITHUB_BASE": base}

def _headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

# --------- Branch validation ---------
BRANCH_RE = re.compile(r"^(?!/)(?!.*//)(?!.*\.\.)(?!.*\.$)[A-Za-z0-9._/-]{1,255}$")
STAGE_A_RE = re.compile(r"^stage-a/\d{8}-[a-z0-9-]{1,48}(-\d+)?$")

def validate_branch_name(branch: str) -> None:
    if not branch or not BRANCH_RE.match(branch):
        raise HTTPException(400, "Invalid branch name")
    if not STAGE_A_RE.match(branch):
        raise HTTPException(400, "Branch is not a Stage-A branch")

# --------- HTTP robustness ---------
async def _request_with_retries(method, url: str, *, max_retries: int = 2, backoff_start: float = 0.5, **kwargs) -> httpx.Response:
    import asyncio
    backoff = backoff_start
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            resp: httpx.Response = await method(url, **kwargs)
            # Clear rate-limit error
            if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
                raise HTTPException(429, "GitHub rate limit exceeded; wait and retry")
            # Retry 5xx
            if 500 <= resp.status_code < 600 and attempt < max_retries:
                await asyncio.sleep(backoff); backoff *= 2; continue
            return resp
        except httpx.RequestError as e:
            last_exc = e
            if attempt < max_retries:
                await asyncio.sleep(backoff); backoff *= 2; continue
            raise HTTPException(502, f"Network error talking to GitHub: {e!s}")
    if last_exc:
        raise HTTPException(502, f"Network error talking to GitHub: {last_exc!s}")
    raise HTTPException(502, "Unknown network error")

# --------- Helpers ---------
def _sanitize_title(s: str) -> str:
    s = re.sub(r"[\x00-\x1F\x7F\r\n\t]+", " ", (s or "")).strip()
    return (s[:120] or "Stage B Promote")

def _owner_repo(repo: str) -> tuple[str, str]:
    owner, name = repo.split("/", 1)
    return owner, name

async def _get_ref_sha(cfg: Dict[str, str], branch: str) -> Optional[str]:
    url = f"{cfg['GITHUB_API']}/repos/{cfg['GITHUB_REPO']}/git/ref/heads/{branch}"
    async with httpx.AsyncClient(timeout=20) as c:
        r = await _request_with_retries(c.get, url, headers=_headers(cfg["GITHUB_TOKEN"]))
    if r.status_code == 200:
        return r.json()["object"]["sha"]
    if r.status_code == 404:
        return None
    r.raise_for_status()

async def _find_existing_pr(cfg: Dict[str, str], branch: str) -> Optional[int]:
    owner, _ = _owner_repo(cfg["GITHUB_REPO"])
    # Search open PRs with head=owner:branch (base filter is optional)
    url = f"{cfg['GITHUB_API']}/repos/{cfg['GITHUB_REPO']}/pulls"
    params = {"state": "open", "head": f"{owner}:{branch}"}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await _request_with_retries(c.get, url, headers=_headers(cfg["GITHUB_TOKEN"]), params=params)
    if r.status_code == 200:
        items = r.json()
        if items:
            return int(items[0]["number"])
        return None
    r.raise_for_status()

async def _create_pr(cfg: Dict[str, str], branch: str, title: str) -> int:
    url = f"{cfg['GITHUB_API']}/repos/{cfg['GITHUB_REPO']}/pulls"
    body = {"title": _sanitize_title(title), "head": branch, "base": cfg["GITHUB_BASE"]}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await _request_with_retries(c.post, url, headers=_headers(cfg["GITHUB_TOKEN"]), json=body)
    if r.status_code in (200, 201):
        return int(r.json()["number"])
    if r.status_code == 422 and "A pull request already exists" in r.text:
        # fall back to finder
        pr = await _find_existing_pr(cfg, branch)
        if pr is not None:
            return pr
    r.raise_for_status()

async def _tag_exists(cfg: Dict[str, str], tag: str) -> bool:
    url = f"{cfg['GITHUB_API']}/repos/{cfg['GITHUB_REPO']}/git/ref/tags/{tag}"
    async with httpx.AsyncClient(timeout=20) as c:
        r = await _request_with_retries(c.get, url, headers=_headers(cfg["GITHUB_TOKEN"]))
    if r.status_code == 200:
        return True
    if r.status_code == 404:
        return False
    r.raise_for_status()

async def _create_lightweight_tag(cfg: Dict[str, str], tag: str, sha: str) -> None:
    url = f"{cfg['GITHUB_API']}/repos/{cfg['GITHUB_REPO']}/git/refs"
    body = {"ref": f"refs/tags/{tag}", "sha": sha}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await _request_with_retries(c.post, url, headers=_headers(cfg["GITHUB_TOKEN"]), json=body)
    if r.status_code not in (200, 201):
        r.raise_for_status()

# --------- Request model ---------
class PromoteRequest(BaseModel):
    branch: str
    title: Optional[str] = None
    tag: Optional[str] = None  # optional; if provided we ensure/create lightweight tag on branch head

# --------- Routes ---------
@router.post("/promote")
async def promote(req: PromoteRequest):
    # 1) env
    try:
        cfg = validate_env()
    except RuntimeError as e:
        raise HTTPException(500, f"Integrator misconfigured: {e}")

    # 2) validate branch input
    validate_branch_name(req.branch)

    # 3) resolve branch head sha
    sha = await _get_ref_sha(cfg, req.branch)
    if not sha:
        raise HTTPException(404, f"Branch '{req.branch}' not found")

    # 4) idempotent PR: reuse existing PR if present
    pr_num = await _find_existing_pr(cfg, req.branch)
    if pr_num is None:
        pr_num = await _create_pr(cfg, req.branch, req.title or f"Promote {req.branch} → {cfg['GITHUB_BASE']}")

    # 5) optional idempotent tag
    tag_created = None
    if req.tag:
        safe_tag = re.sub(r"[^A-Za-z0-9._/-]", "-", req.tag).strip("/")
        if not safe_tag or safe_tag.endswith(".") or ".." in safe_tag or "//" in safe_tag:
            raise HTTPException(400, "Invalid tag name")
        exists = await _tag_exists(cfg, safe_tag)
        if not exists:
            await _create_lightweight_tag(cfg, safe_tag, sha)
            tag_created = safe_tag
        else:
            tag_created = safe_tag  # already exists; return it

    return {"ok": True, "pr_number": pr_num, "sha": sha, "tag": tag_created}
