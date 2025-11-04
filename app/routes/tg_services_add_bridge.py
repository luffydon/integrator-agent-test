import json
import re
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from app.models.service_add import ServiceAddRequest, ServiceAddResult
from app.services.service_store import ServiceStore

router = APIRouter(prefix="/telegram/services", tags=["telegram", "services"])

class TgText(BaseModel):
    text: str = Field(..., description="Raw Telegram message text")
    chat_id: Optional[str] = Field(None, description="Telegram chat id (optional)")
    user_id: Optional[str] = Field(None, description="Telegram user id (optional)")

FENCE_RX = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
CMD_RX = re.compile(r"^/addservice\b", re.IGNORECASE)

def extract_json_block(text: str) -> str:
    m = FENCE_RX.search(text)
    if m:
        return m.group(1).strip()
    if CMD_RX.search(text):
        return CMD_RX.sub("", text, count=1).strip()
    return text.strip()

@router.post("/add", response_model=ServiceAddResult)
async def telegram_service_add(payload: TgText):
    raw = extract_json_block(payload.text or "")
    if not raw:
        raise HTTPException(status_code=400, detail="No JSON payload found after /addservice")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    if "service" in data:
        req_data = data
    else:
        req_data = {"service": data}

    try:
        req = ServiceAddRequest(**req_data)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Schema validation failed: {e}")

    try:
        store = ServiceStore()
        sid, slug, path = store.put(req.service.dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store service: {e}")

    return ServiceAddResult(id=sid, slug=slug, stored_path=path, message="Service stored")
