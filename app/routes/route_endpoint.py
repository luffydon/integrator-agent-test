from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from typing import Any, Dict

from app.agents.service_agent import handle_message
from app.security import require_router_secret

router = APIRouter()

@router.post(
    "/route",
    # This 'dependencies' parameter is what tells Swagger to use the security scheme
    dependencies=[Depends(require_router_secret)]
)
async def route_endpoint(
    body: Dict[str, Any],
    req: Request,
) -> JSONResponse:
    """
    Handles incoming messages via the /route endpoint.
    Requires X-Router-Secret header for authorization.
    """
    user_id = str(body.get("user_id", "anon"))
    text = str(body.get("message", "") or "")

    handled, output = await handle_message(user_id, text, channel="http")

    return JSONResponse({"handled": handled, "output": output})