from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import zipfile, io, os, re
from datetime import datetime
from app.integrator.branch_pusher import validate_env, create_branch, push_files, BranchCreateError, PushError
from httpx import RequestError

router = APIRouter(prefix="/integrations/stage-a", tags=["integrations-stage-a"])

MAX_ZIP_MB = int(os.environ.get("INTEGRATOR_MAX_ZIP_MB", "25"))
MAX_FILE_MB = int(os.environ.get("INTEGRATOR_MAX_FILE_MB", "5"))
MAX_FILE_COUNT = int(os.environ.get("INTEGRATOR_MAX_FILE_COUNT", "500"))

_slug_re = re.compile(r"[^a-z0-9-]+")
_branch_pat = re.compile(r"^stage-a/\d{8}-[a-z0-9-]{1,48}(-\d+)?$")

def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = _slug_re.sub("", s)
    return s[:48] or "patch"

def _extract_zip(buf: bytes):
    files = []
    with zipfile.ZipFile(io.BytesIO(buf)) as z:
        for zi in z.infolist():
            if zi.is_dir() or zi.file_size == 0:
                continue
            if zi.file_size > MAX_FILE_MB * 1024 * 1024:
                raise HTTPException(413, f"File too large: {zi.filename}")
            data = z.read(zi)
            files.append((zi.filename, data))
            if len(files) > MAX_FILE_COUNT:
                raise HTTPException(413, f"Too many files in ZIP (limit {MAX_FILE_COUNT})")
    if not files:
        raise HTTPException(400, "ZIP contained no usable files")
    return files

@router.post("/submit-zip")
async def submit_zip(title: str = Form(...), upload: UploadFile = File(...)):
    try:
        cfg = validate_env()
    except RuntimeError as e:
        raise HTTPException(500, f"Integrator misconfigured: {e}")

    if not upload.filename or not upload.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Please upload a .zip file")
    content = await upload.read()
    if len(content) > MAX_ZIP_MB * 1024 * 1024:
        raise HTTPException(413, f"ZIP exceeds {MAX_ZIP_MB} MB limit")
    try:
        files = _extract_zip(content)
    except zipfile.BadZipFile:
        raise HTTPException(400, "Invalid ZIP file")

    date = datetime.utcnow().strftime("%Y%m%d")
    slug = slugify(title)
    base_branch = f"stage-a/{date}-{slug}"

    branch = base_branch
    try:
        created = await create_branch(cfg, branch)
        if not created:
            branch = base_branch + "-2"
            await create_branch(cfg, branch)
    except BranchCreateError as e:
        raise HTTPException(404, str(e))

    try:
        res = await push_files(cfg, branch, files, title)
    except RequestError as e:
        raise HTTPException(502, f"Network error: {e}")
    except PushError as e:
        raise HTTPException(502, str(e))

    return {"ok": True, "branch": branch, "files_written": res["written"], "files_skipped": res["skipped"]}
