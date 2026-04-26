from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from my_agent.agent import agent_manager
from autogen_agentchat.messages import (
    MultiModalMessage, 
    TextMessage, 
    ModelClientStreamingChunkEvent
)
from autogen_agentchat.base import TaskResult
from autogen_core import Image as AGImage
from PIL import Image

import os
import json
import asyncio
import uuid
import logging
import base64
from io import BytesIO
from datetime import datetime, timezone
from typing import Optional

from utils import generate_jwt, validate_jwt, save_feedback, send_email, extract_text_from_attachment
from zijus_tools import set_websocket_sender

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
templates = Jinja2Templates(directory="templates")

APP_NAME = os.getenv("APP_NAME", "ZijusAutoGenApp")
ZIJUS_JAVASCRIPT = "https://cdn.jsdelivr.net/gh/zijus/zijus-chat-ui@main/dist/zijus-webclient-v0.1.0.js"
ZIJUS_CONFIG_ENCODED = os.getenv("ZIJUS_CONFIG_ENCODED", "")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"agent_name": APP_NAME, "zijus_config": ZIJUS_CONFIG_ENCODED, "zijus_javascript": ZIJUS_JAVASCRIPT}
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

    # 1. Inject Zijus Tools WebSockets Sender
    async def sender(msg: dict):
        await websocket.send_json(msg)
    set_websocket_sender(sender)

    # 2. State tracking for Barge-in Interruption
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

    # 3. Background AutoGen Execution Task
    async def process_agent_request(request_message, m_id: str):
        response_m_id = str(uuid.uuid4())
        try:
            # Fetch the isolated AutoGen agent for this specific session
            agent = agent_manager.get_agent(session_id)
            
            async for message in agent.run_stream(task=request_message):
                if isinstance(message, TaskResult):
                    continue
                
                # Render streaming text chunks directly to the UI
                if isinstance(message, ModelClientStreamingChunkEvent):
                    if message.content:
                        await websocket.send_json({
                            "source": "assistant",
                            "content": message.content,
                            "m_id": response_m_id,
                            "type": "TextMessage", 
                            "ts": datetime.now(timezone.utc).isoformat()
                        })

            await websocket.send_json({
                "source": "assistant", "type": "FinalMessage", 
                "m_id": response_m_id, "ts": datetime.now(timezone.utc).isoformat()
            })

        except asyncio.CancelledError:
            logger.info("AutoGen run cancelled by user interruption.")
        except Exception as e:
            logger.error(f"AutoGen execution error: {e}")
            await websocket.send_json({"source": "assistant", "type": "error", "content": "Error processing request."})

    # 4. Main Event Loop
    try:
        while True:
            data = await websocket.receive_text()
            try: data_json = json.loads(data)
            except json.JSONDecodeError: continue

            msg_type = data_json.get('type')
            m_id = data_json.get('m_id', str(uuid.uuid4()))

            if msg_type in ['session', None]: continue
            if msg_type == 'feedback': await save_feedback(); continue
            if msg_type == 'send_email': await send_email(); continue

            # Handle Audio Barge-in
            if msg_type == 'AudioMessage':
                await cancel_running_task(reason="User started speaking")
                continue

            # Handle UI Widget Events (Form Submissions, Button Clicks)
            if msg_type == "WidgetEvent":
                await cancel_running_task(reason="User interacted with a widget")
                payload = data_json.get("widgetEvent", {}).get("payload", {})
                text_content = "\n".join(f"{k}: {v}" for k, v in payload.items()).strip()
                if text_content:
                    request_message = TextMessage(content=f"[User Submitted Widget]:\n{text_content}", source="user")
                    current_ai_task = asyncio.create_task(process_agent_request(request_message, m_id))
                continue

            # Handle Text & Multimodal Attachments
            if msg_type == 'TextMessage':
                await cancel_running_task(reason="User typed a message")
                content_text = data_json.get('content', '')
                request_message = None

                if 'attachment' in data_json:
                    att = data_json['attachment']
                    att_data = base64.b64decode(att['data'])
                    mime = att.get('type', 'application/octet-stream')

                    if mime.startswith('image/'):
                        try:
                            pil_image = Image.open(BytesIO(att_data))
                            request_message = MultiModalMessage(content=[content_text, AGImage(pil_image)], source="user")
                        except Exception as e:
                            logger.error(f"Image error: {e}")
                    else:
                        extracted_text = await extract_text_from_attachment(BytesIO(att_data), mime)
                        content_text += f"\n\n[Attachment Content]:\n{extracted_text}"
                        request_message = TextMessage(content=content_text, source="user")
                elif content_text:
                    request_message = TextMessage(content=content_text, source="user")

                if request_message:
                    current_ai_task = asyncio.create_task(process_agent_request(request_message, m_id))

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")