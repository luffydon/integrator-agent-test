import pytest, httpx, respx, base64
from app.integrator import branch_pusher as bp

CFG = {
    "GITHUB_API": "https://api.github.com",
    "GITHUB_TOKEN": "t",
    "GITHUB_REPO": "o/r",
}

def test_branch_name_valid_and_invalid():
    bp.validate_branch_name("feature/x")
    with pytest.raises(bp.BranchCreateError):
        bp.validate_branch_name("bad..name")

def test_path_normalize_and_encode():
    assert bp.normalize_path("a//b/../c.txt") == "a/c.txt"
    with pytest.raises(bp.PushError):
        bp.normalize_path("../evil")
    enc = bp.encode_contents_path("dir/file name.txt")
    assert "%20" in enc

def test_commit_message_sanitization():
    m = bp._sanitize_commit_message("Hello\nWorld\t")
    assert " " in m and len(m) <= 120

@respx.mock
@pytest.mark.asyncio
async def test_put_file_create_and_skip():
    path = "dir/file.txt"
    url = f"{CFG['GITHUB_API']}/repos/{CFG['GITHUB_REPO']}/contents/{path}"
    body = b"hello"
    # Not found then create
    respx.get(url).mock(return_value=httpx.Response(404))
    respx.put(url).mock(return_value=httpx.Response(201))
    ok = await bp.put_file(CFG, "feature/x", path, body, "msg")
    assert ok is True
    # Identical skip
    respx.get(url).mock(return_value=httpx.Response(200, json={"content": base64.b64encode(body).decode(), "sha": "abc"}))
    ok = await bp.put_file(CFG, "feature/x", path, body, "msg")
    assert ok is False

@respx.mock
@pytest.mark.asyncio
async def test_rate_limit_handling():
    url = "https://api.github.com/repos/o/r/contents/x"
    respx.get(url).mock(return_value=httpx.Response(403, headers={"X-RateLimit-Remaining":"0"}))
    async with httpx.AsyncClient() as c:
        with pytest.raises(bp.PushError):
            await bp._request_with_retries(c.get, url)
