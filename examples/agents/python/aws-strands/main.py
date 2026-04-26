import os
import json
import base64
import logging
import uuid
import asyncio
from io import BytesIO
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# --- Local Imports ---
from my_agent.agent import get_agent
from utils import generate_jwt, validate_jwt, extract_text_from_attachment, save_feedback, send_email

# --- Zijus Imports ---
from zijus_tools import set_websocket_sender

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
templates = Jinja2Templates(directory="templates")

APP_NAME = os.getenv("APP_NAME", "ZijusStrandsApp")
ZIJUS_JAVASCRIPT = "https://cdn.jsdelivr.net/gh/zijus/zijus-chat-ui@main/dist/zijus-webclient-v0.1.0.js"
ZIJUS_CONFIG_ENCODED = os.getenv("ZIJUS_CONFIG_ENCODED", "")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "agent_name": APP_NAME, 
        "zijus_config": ZIJUS_CONFIG_ENCODED, 
        "zijus_javascript": ZIJUS_JAVASCRIPT
    })

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    import httpx
    
    token = websocket.query_params.get("token", "")
    session_id = websocket.query_params.get("session_id", "")
    
    payload = await validate_jwt(token) if token else None
    user_id = payload.get("user_id", "anon") if payload else "anon"
    session_id = session_id or (payload.get("session_id") if payload else f"sess-{uuid.uuid4()}")
    
    new_token = await generate_jwt(session_id) if not payload else token

    await websocket.accept()
    await websocket.send_json({"type": "session", "token": new_token})

    async def sender(msg: dict):
        await websocket.send_json(msg)
    set_websocket_sender(sender)

    # 1. Provide an AsyncClient that stays alive for the whole session
    async with httpx.AsyncClient() as http_client:
        # 2. Pass it to the agent to bypass the proxies crash
        agent = get_agent(session_id=session_id, user_id=user_id, http_client=http_client) # type: ignore

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

        async def process_agent_request(input_payload, m_id: str):
            response_m_id = str(uuid.uuid4())
            try:
                async for event in agent.stream_async(input_payload):
                    if "data" in event:
                        chunk_content = event["data"]
                        if chunk_content:
                            await websocket.send_json({
                                "source": "assistant", "content": chunk_content, "m_id": response_m_id,
                                "type": "TextMessage", "ts": datetime.now(timezone.utc).isoformat()
                            })
                    elif event.get("force_stop", False):
                        reason = event.get("force_stop_reason", "Unknown")
                        logger.info(f"Strands stream stopped. Reason: {reason}")

                await websocket.send_json({
                    "source": "assistant", "type": "FinalMessage", 
                    "m_id": response_m_id, "ts": datetime.now(timezone.utc).isoformat()
                })

            except asyncio.CancelledError:
                logger.info("Strands run cancelled by user interruption.")
            except Exception as e:
                logger.error(f"Strands execution error: {e}")
                await websocket.send_json({"source": "assistant", "type": "error", "content": "Error processing request."})

        try:
            while True:
                data = await websocket.receive_text()
                try: data_json = json.loads(data)
                except json.JSONDecodeError: continue

                if 'type' not in data_json: continue

                m_id = data_json.get('m_id', str(uuid.uuid4()))
                msg_type = data_json.get('type')

                if msg_type in ['session', None]: continue
                
                if msg_type == 'feedback':
                    await save_feedback()
                    continue

                if msg_type == 'send_email':
                    await send_email()
                    continue

                if msg_type == 'AudioMessage':
                    await cancel_running_task(reason="User started speaking")
                    continue

                if msg_type == "WidgetEvent":
                    await cancel_running_task(reason="User interacted with a widget")
                    payload = data_json.get("widgetEvent", {}).get("payload", {})
                    text_content = "\n".join(f"{k}: {v}" for k, v in payload.items()).strip()
                    if text_content:
                        current_ai_task = asyncio.create_task(
                            process_agent_request(f"[User Submitted Form/Widget]:\n{text_content}", m_id)
                        )
                    continue

                if msg_type == 'TextMessage':
                    await cancel_running_task(reason="User typed a message")
                    prompt_text = data_json.get('content', '')
                    input_payload = prompt_text

                    if 'attachment' in data_json:
                        att = data_json['attachment']
                        att_type = att.get('type', '')
                        
                        if att_type.startswith('image/'):
                            try:
                                img_format = att_type.split('/')[-1]
                                input_payload = [{
                                    "role": "user",
                                    "content": [
                                        {"image": {"format": img_format, "source": {"bytes": base64.b64decode(att['data'])}}},
                                        {"text": prompt_text}
                                    ]
                                }]
                            except Exception as e:
                                logger.error(f"Image error: {e}")
                        else:
                            try:
                                att_data = base64.b64decode(att['data'])
                                extracted_text = await extract_text_from_attachment(BytesIO(att_data), att_type) 
                                if isinstance(input_payload, str):
                                    input_payload += f"\n\n[Attachment Content]:\n{extracted_text}"
                            except Exception: pass

                    if input_payload:
                        current_ai_task = asyncio.create_task(process_agent_request(input_payload, m_id))

        except WebSocketDisconnect:
            logger.info(f"Client disconnected: {session_id}")
            
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)