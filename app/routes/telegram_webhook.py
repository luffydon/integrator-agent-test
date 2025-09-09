# app/routes/telegram_webhook.py

from __future__ import annotations
import os
from typing import Any, Dict, Optional
import httpx
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.agents.service_agent import handle_message
from app.integrations.telegram import TelegramClient
from app.core import session_store as sess
from app.core import agent_manager as agents_mgr
from app.agent_models import AgentCreateRequest
from app.services import router_service as ROUTER
from app.agents import info_only_agent as INFO
from app.clients import backend_api as be  # <-- Import backend_api

router = APIRouter()

WEBHOOK_SECRET   = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
DEFAULT_AGENT_ID = os.getenv("DEFAULT_AGENT_ID")

@router.post("/telegram/webhook")
async def telegram_webhook(req: Request) -> JSONResponse:
    chat_id = None
    output = ""
    msg = {} 
    
    try:
        if WEBHOOK_SECRET:
            if req.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
                return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

        update: Dict[str, Any] = await req.json()
        client = TelegramClient()
        
        if "callback_query" in update:
            callback_query = update["callback_query"]
            chat_id = str(callback_query["message"]["chat"]["id"])
            user_id = str(callback_query["from"]["id"])
            data = callback_query["data"]
            msg = callback_query["message"]
            
            try:
                await client.answer_callback_query(callback_query["id"])
            except Exception:
                pass
            
            info_cb = await INFO.handle_callback(str(chat_id), user_id, data, client)
            if info_cb and info_cb.get("handled"):
                if info_cb.get("output"):
                    await client.send_message(chat_id, info_cb["output"])
                return JSONResponse({"ok": True})
            text = data
        
        else:
            msg: Optional[Dict[str, Any]] = update.get("message") or update.get("edited_message")

            if not msg or not msg.get("text"):
                return JSONResponse({"ok": True})

            chat = msg.get("chat", {})
            chat_id = str(chat.get("id"))
            from_user = msg.get("from", {})
            user_id = str(from_user.get("id") or chat_id or "anon")
            text = (msg.get("text") or "").strip()

        print(f"📥 Incoming message from user {user_id} in chat {chat_id}: {text}")

        session = sess.get_session(chat_id)
        state = session.get("state")
    
        if state and state.startswith("svc_create_"):
            resp = await ROUTER.handle_agent_message(chat_id, user_id, text)
            await client.send_message(chat_id, resp["reply"])
            return JSONResponse({"ok": True})
        
        if text.startswith("/"):
            # Handle dynamic commands that match a category name (e.g., /food, /tech)
            command_body = text[1:].strip().lower()
            available_categories = await be.get_non_empty_categories_async()
            normalized_categories = [cat.lower() for cat in available_categories]

            if command_body in normalized_categories:
                # The command is a category, so we'll treat it as a browse request.
                info_resp = await INFO.handle_message(chat_id, command_body, client)
                if info_resp and info_resp.get("output"):
                    await client.send_message(chat_id, info_resp["output"], reply_to_message_id=msg.get("message_id"))
                return JSONResponse({"ok": True})
            # --- END NEW LOGIC ---
            
            session = sess.get_session(chat_id)
            state = session.get("state")
            
            if (
                text in {"/menu", "/start"} or
                re.search(r"\b(menu|categories|what do you have|what services do you have)\b", text, re.I) or
                re.search(r"\b(food|restaurant|restaurants|dining|transport|taxi|bike|bicycle|scooter)\b", text, re.I)
            ):
                info_resp = await INFO.handle_message(chat_id, text, client)
                if info_resp and info_resp.get("output"):
                    await client.send_message(chat_id, info_resp["output"], reply_to_message_id=msg.get("message_id"))
                return JSONResponse({"ok": True})
            
            if text in {"/add_service", "/add", "/service_add", "/new"} or re.search(r"\b(add|create|new)\s*service", text, re.I):
                resp = await ROUTER.handle_agent_message(chat_id, user_id, text)
                await client.send_message(chat_id, resp["reply"])
                return JSONResponse({"ok": True})

            if text.startswith("/create"):
                sess.update_session(chat_id, {"state": "create_name", "form_data": {}})
                await client.send_message(chat_id, "🆕 **Create a New Agent**\n\nEnter a name for your agent:")
                return JSONResponse({"ok": True})
            
            if text.startswith("/agents"):
                items = agents_mgr.list_agents(include_archived=False)
                public = [a for a in items if a.visibility in ("public", "unlisted")]
                if not public:
                    await client.send_message(chat_id, "There are no public agents available at the moment.")
                    return JSONResponse({"ok": True})

                keyboard = []
                for i in range(0, len(public), 2):
                    row = []
                    row.append({"text": f"{public[i].name}", "callback_data": f"/use {public[i].id}"})
                    if i + 1 < len(public):
                        row.append({"text": f"{public[i+1].name}", "callback_data": f"/use {public[i+1].id}"})
                    keyboard.append(row)

                reply_markup = {"inline_keyboard": keyboard}
                await client.send_message(chat_id, "Please choose a bot to interact with:", reply_markup=reply_markup)
                return JSONResponse({"ok": True})

            if text.startswith("/agent") or text.startswith("/whoami"):
                active_agent_id = sess.get_active(chat_id) or DEFAULT_AGENT_ID
                name = active_agent_id or "(none)"
                await client.send_message(chat_id, f"Active agent: {name}", reply_to_message_id=msg.get("message_id"))
                return JSONResponse({"ok": True})

            if text.startswith("/use "):
                token = text.split(" ", 1)[1].strip()
                target = next((a for a in agents_mgr.list_agents(False) if a.id == token or a.name == token), None)
                if not target:
                    await client.send_message(chat_id, "Agent not found. Use /agents to list.", reply_to_message_id=msg.get("message_id"))
                else:
                    sess.set_active(chat_id, target.id)
                    await client.send_message(chat_id, f"✅ Now using: {target.name} ({target.id})", reply_to_message_id=msg.get("message_id"))
                return JSONResponse({"ok": True})

            if text.startswith("/clear"):
                sess.clear_active(chat_id)
                await client.send_message(chat_id, "Cleared agent for this chat.", reply_to_message_id=msg.get("message_id"))
                return JSONResponse({"ok": True})

        if re.search(r"\b(add|create|new)\s*service", text, re.I):
            resp = await ROUTER.handle_agent_message(chat_id, user_id, text)
            await client.send_message(chat_id, resp["reply"])
            return JSONResponse({"ok": True})
        
        if state == "create_name":
            session["form_data"] = {"name": text}
            session["state"] = "create_description"
            sess.update_session(chat_id, session)
            await client.send_message(chat_id, "📝 Enter agent description:")
            return JSONResponse({"ok": True})

        if state == "create_description":
            session["form_data"]["description"] = text
            session["state"] = "create_visibility"
            sess.update_session(chat_id, session)
            await client.send_message(chat_id, "🔒 Set visibility: `public`, `unlisted`, or `private`?")
            return JSONResponse({"ok": True})

        if state == "create_visibility":
            visibility = text.lower()
            if visibility not in ["public", "unlisted", "private"]:
                await client.send_message(chat_id, "❌ Invalid. Please enter `public`, `unlisted`, or `private`.")
                return JSONResponse({"ok": True})
            
            session["form_data"]["visibility"] = visibility
            create_req = AgentCreateRequest(**session["form_data"])
            agent = agents_mgr.create_agent(create_req)
            await client.send_message(chat_id, f"✅ Agent '{agent.name}' created and you Agent_id is `{agent.id}`.", reply_to_message_id=msg.get("message_id"))
            sess.clear_session_state(chat_id)
            return JSONResponse({"ok": True})

        active_agent_id = sess.get_active(chat_id) or DEFAULT_AGENT_ID
        if not active_agent_id:
            await client.send_message(chat_id, "Hello! How can I assist you today? If you're looking for services to book, just let me know!")
            return JSONResponse({"ok": True})

        if text:
            agents_mgr.log_message(active_agent_id, f"TG[{chat_id}]: {text}", user_id=user_id, tag="msg")

        handled, output = await handle_message(user_id=user_id, text=text, channel="telegram")
        
        if output:
            success = await client.send_message(chat_id, output, reply_to_message_id=msg.get("message_id"))
            if success:
                print(f"✅ Sent message to Telegram chat {chat_id}: {output}")

        return JSONResponse({"ok": True, "handled": bool(handled)})

    except httpx.ConnectError as e:
        print(f"--- CAUGHT CONNECTION ERROR ---\n{e}\n-----------------\n")
        print("\n--- Outgoing Telegram Message ---")
        print(f"Chat ID: {chat_id}")
        print(f"Message: {output}")
        return JSONResponse({"ok": True, "error_handled": "ConnectError"})
        
    except Exception as e:
        import traceback
        print(f"--- CAUGHT UNEXPECTED ERROR ---\n{e}\n-----------------\n")
        traceback.print_exc()
        
        try:
            update = await req.json()
            msg_inner = update.get("message", {}) or update.get("callback_query", {}).get("message", {})
            chat_id_inner = msg_inner.get("chat", {}).get("id")
            if chat_id_inner:
                error_client = TelegramClient()
                await error_client.send_message(chat_id_inner, "Sorry, I encountered an error and couldn't process your request.")
        except Exception as notification_error:
            print(f"--- FAILED TO NOTIFY USER OF ERROR ---\n{notification_error}\n-----------------")
            print("\n--- Outgoing Telegram Message ---")
            print(f"Chat ID: {chat_id}")
            print(f"Message: {output}")
            
        return JSONResponse({"ok": True, "error_handled": True})