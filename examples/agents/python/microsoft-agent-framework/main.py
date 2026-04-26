from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from agent_framework import Message
from contextlib import asynccontextmanager
import os
import json
import asyncio
import uuid
import logging
import base64
from utils import generate_jwt, validate_jwt, save_feedback, send_email, extract_text_from_attachment
from io import BytesIO
from datetime import datetime, timezone
from typing import Optional

# Zijus UI Tools
from zijus_tools import set_websocket_sender

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

from my_agent.agent import root_agent

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await root_agent.close()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

templates = Jinja2Templates(directory="templates")

APP_NAME = os.getenv("APP_NAME", "ZijusMsAgentApp")
ZIJUS_JAVASCRIPT = "https://cdn.jsdelivr.net/gh/zijus/zijus-chat-ui@main/dist/zijus-webclient-v0.1.0.js"
ZIJUS_CONFIG_ENCODED = os.getenv("ZIJUS_CONFIG_ENCODED", "")

def extract_text_from_chunk(chunk):
    if hasattr(chunk, 'text') and chunk.text: return chunk.text
    if hasattr(chunk, 'content'):
        if hasattr(chunk.content, 'text') and chunk.content.text: return chunk.content.text
        elif isinstance(chunk.content, str): return chunk.content
    if hasattr(chunk, 'delta'):
        if hasattr(chunk.delta, 'text') and chunk.delta.text: return chunk.delta.text
        if hasattr(chunk.delta, 'content') and hasattr(chunk.delta.content, 'text'): return chunk.delta.content.text
    try:
        chunk_str = str(chunk)
        if chunk_str and chunk_str not in ['', 'None']: return chunk_str
    except: pass
    return None

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(
        request=request,  # Must be explicitly named now!
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

    # Inject Zijus Tools WebSockets Sender
    async def sender(msg: dict):
        await websocket.send_json(msg)
    set_websocket_sender(sender)

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

    async def process_agent_request(chat_message: Message, m_id: str):
        response_m_id = str(uuid.uuid4())
        try:
            async for chunk in root_agent.run_stream(chat_message, session_id=session_id):
                text_content = extract_text_from_chunk(chunk)
                if text_content:
                    await websocket.send_json({
                        "source": "assistant", "content": text_content, "m_id": response_m_id,
                        "type": "TextMessage", "ts": datetime.now(timezone.utc).isoformat()
                    })

            await websocket.send_json({
                "source": "assistant", "type": "FinalMessage", 
                "m_id": response_m_id, "ts": datetime.now(timezone.utc).isoformat()
            })

        except asyncio.CancelledError:
            logger.info("Agent run cancelled by user interruption.")
        except Exception as e:
            logger.error(f"Agent execution error: {e}")
            await websocket.send_json({"source": "assistant", "type": "error", "content": "Error processing request."})

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

            if msg_type == 'AudioMessage':
                await cancel_running_task(reason="User started speaking")
                continue
            
            if msg_type == "WidgetEvent":
                await cancel_running_task(reason="User interacted with a widget")
                payload = data_json.get("widgetEvent", {}).get("payload", {})
                text_content = "\n".join(f"{k}: {v}" for k, v in payload.items()).strip()
                if text_content:
                    chat_msg = Message(role="user", contents=[f"[User Submitted Widget]:\n{text_content}"])
                    current_ai_task = asyncio.create_task(process_agent_request(chat_msg, m_id))
                continue

            if msg_type == 'TextMessage':
                await cancel_running_task(reason="User typed a message")
                content_text = data_json.get('content', '')
                contents = []

                if 'attachment' in data_json:
                    att = data_json['attachment']
                    try:
                        mime = att.get('type', 'application/octet-stream')
                        
                        if mime.startswith('image/'):
                            # Base64 Multimodal format expected by standard chat completion
                            contents.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{att['data']}"}
                            })
                        else:
                            att_data = base64.b64decode(att['data'])
                            extracted_text = await extract_text_from_attachment(BytesIO(att_data), mime) 
                            content_text += f"\n\n[Attachment Content]:\n{extracted_text}"
                    except Exception as e:
                        logger.error(f"Attachment error: {e}")

                if content_text:
                    contents.append(content_text)

                if contents:
                    chat_msg = Message(role="user", contents=contents)
                    current_ai_task = asyncio.create_task(process_agent_request(chat_msg, m_id))

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")