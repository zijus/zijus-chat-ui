from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import os
import json
import uuid
import logging
import base64
import asyncio
from datetime import datetime, timezone
from typing import Optional

from my_agent.agent import root_agent, build_message_payload
from utils import generate_jwt, validate_jwt, save_feedback, send_email, extract_text_from_attachment
from zijus_tools import set_websocket_sender

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
templates = Jinja2Templates(directory="templates")

APP_NAME = os.getenv("APP_NAME", "ZijusLangChainApp")
ZIJUS_JAVASCRIPT = "https://cdn.jsdelivr.net/gh/zijus/zijus-chat-ui@main/dist/zijus-webclient-v0.1.0.js"
ZIJUS_CONFIG_ENCODED = os.getenv("ZIJUS_CONFIG_ENCODED", "")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html", 
        context={
            "agent_name": APP_NAME,
            "zijus_config": ZIJUS_CONFIG_ENCODED,
            "zijus_javascript": ZIJUS_JAVASCRIPT
        }
    )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token", "")
    session_id = websocket.query_params.get("session_id", "")
    
    payload = await validate_jwt(token) if token else None
    user_id = payload.get("user_id", "anon") if payload else "anon"
    session_id = session_id or (payload.get("session_id") if payload else f"sess-{uuid.uuid4()}")
    
    new_token = await generate_jwt(session_id) if not payload else token

    await websocket.accept()
    await websocket.send_json({"type": "session", "token": new_token})

    # 1. Inject WebSocket Sender for Zijus Tools 
    async def sender(msg: dict):
        await websocket.send_json(msg)
    set_websocket_sender(sender)

    # 2. State Tracking for Barge-in Interruption
    current_ai_task: Optional[asyncio.Task] = None

    async def cancel_running_task(reason: str):
        nonlocal current_ai_task
        if current_ai_task and not current_ai_task.done():
            logger.info(f"Interrupting AI generation: {reason}")
            current_ai_task.cancel()
            try:
                await websocket.send_json({
                    "source": "assistant",
                    "type": "InterruptMessage",
                    "ts": datetime.now(timezone.utc).isoformat()
                })
            except Exception: pass

    # 3. Background Agent Execution Task
    async def process_agent_request(user_input: dict | str, m_id: str):
        response_m_id = str(uuid.uuid4())
        payload = build_message_payload(user_input)
        config = {"configurable": {"thread_id": session_id}}
        
        # LangGraph stream mode "messages" returns individual message chunks
        stream_modes = ["messages"] 

        try:
            async for smode, chunk in root_agent.astream(payload, stream_mode=stream_modes, config=config): # type: ignore
                if smode == "messages":
                    # Extract the chunk part (index 0) from the tuple returned by LangGraph
                    msg_chunk = chunk[0]
                    
                    # 1. Filter out internal Tool execution messages
                    if getattr(msg_chunk, "type", "") == "tool":
                        continue
                        
                    # 2. Only stream text chunks authored by the AI to the UI
                    if hasattr(msg_chunk, "content") and isinstance(msg_chunk.content, str) and msg_chunk.content: # type: ignore
                        # LangChain streams AIMessageChunks. Ensure it's not a tool call dict
                        if getattr(msg_chunk, "tool_calls", None) or getattr(msg_chunk, "tool_call_chunks", None):
                            continue
                            
                        await websocket.send_json({
                            "source": "assistant", "type": "TextMessage", "content": msg_chunk.content, # type: ignore
                            "m_id": response_m_id, "stream_mode": "messages",
                            "ts": datetime.now(timezone.utc).isoformat()
                        })

            await websocket.send_json({
                "source": "assistant", "type": "FinalMessage", 
                "m_id": response_m_id, "ts": datetime.now(timezone.utc).isoformat()
            })

        except asyncio.CancelledError:
            logger.info("LangGraph run cancelled by user interruption.")
        except Exception as e:
            logger.error(f"LangGraph execution error: {e}")
            await websocket.send_json({"source": "assistant", "type": "error", "content": "Error processing request."})

    # 4. Main Event Loop
    try:
        while True:
            raw = await websocket.receive_text()
            try: data_json = json.loads(raw)
            except Exception: continue

            msg_type = data_json.get("type")
            m_id = data_json.get("m_id", str(uuid.uuid4()))

            if msg_type in ["session", None]: continue
            if msg_type == "feedback": await save_feedback(); continue
            if msg_type == "send_email": await send_email(); continue

            # Handle Audio Barge-in
            if msg_type == "AudioMessage":
                await cancel_running_task(reason="User started speaking")
                continue

            # Handle UI Widget Events (Form Submissions, Button Clicks)
            if msg_type == "WidgetEvent":
                await cancel_running_task(reason="User interacted with a widget")
                payload = data_json.get("widgetEvent", {}).get("payload", {})
                text_content = "\n".join(f"{k}: {v}" for k, v in payload.items()).strip()
                if text_content:
                    current_ai_task = asyncio.create_task(
                        process_agent_request(f"[User Submitted Widget]:\n{text_content}", m_id)
                    )
                continue

            # Handle Standard Text Messages & Multimodal Uploads
            if msg_type == "TextMessage":
                await cancel_running_task(reason="User typed a message")
                content_text = data_json.get("content", "")
                
                if "attachment" in data_json:
                    att = data_json["attachment"]
                    if att["type"].startswith("image/"):
                        user_input = {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": content_text},
                                {"type": "image", "base64": att["data"], "mime_type": att["type"]}
                            ]
                        }
                    else:
                        from io import BytesIO
                        extracted = await extract_text_from_attachment(BytesIO(base64.b64decode(att["data"])), att["type"])
                        user_input = f"{content_text}\n\n[Attachment Content]:\n{extracted}"
                else:
                    user_input = content_text

                if user_input:
                    current_ai_task = asyncio.create_task(process_agent_request(user_input, m_id))

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")