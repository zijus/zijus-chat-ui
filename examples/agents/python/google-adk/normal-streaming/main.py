from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.sessions import InMemorySessionService
from google.genai import types
from my_agent.agent import root_agent

import os
import json
import asyncio
import uuid
import logging
import base64
from utils import generate_jwt, validate_jwt, save_feedback, extract_text_from_attachment
from io import BytesIO
from datetime import datetime, timezone
from zijus_tools import set_websocket_sender
from typing import Optional

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static & Templates
#app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

APP_NAME = os.getenv("APP_NAME", "ZijusExampleApp")
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
    # 1. Extract Query Params
    token = websocket.query_params.get("token", "")
    session_id = websocket.query_params.get("session_id", "")
    
    # 2. Handle JWT validation and generation
    payload = await validate_jwt(token) if token else None
    user_id = payload.get("user_id", "anon") if payload else "anon"
    session_id = session_id or (payload.get("session_id") if payload else f"sess-{uuid.uuid4()}")
    
    new_token = await generate_jwt(session_id) if not payload else token

    await websocket.accept()

    # 3. Inject WebSocket Sender for Zijus Tools (Framework Agnostic UI Tools)
    async def sender(msg: dict):
        await websocket.send_json(msg)
    set_websocket_sender(sender)

    await websocket.send_json({"type": "session", "token": new_token})

    # 4. Initialize Agent Framework
    session_service = InMemorySessionService() 
    runner = Runner(app_name=APP_NAME, agent=root_agent, session_service=session_service)

    adk_session = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    if not adk_session:
        await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    # ------------------------------------------

    # State Tracking for Interruption
    current_ai_task: Optional[asyncio.Task] = None


    async def cancel_running_task(reason: str):
        """Cancels the currently generating AI task and notifies the frontend."""
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

    async def process_agent_request(parts: list, m_id: str):
        """Background task to run the agent and stream results back."""
        response_m_id = str(uuid.uuid4())
        run_config = RunConfig(streaming_mode=StreamingMode.SSE, response_modalities=["TEXT"])
        
        try:
            async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=types.Content(role="user", parts=parts), run_config=run_config): # type: ignore
                
                event_parts = getattr(getattr(event, "content", None), "parts", []) or []
                
                # Stream Thoughts (if agent supports reasoning models)
                thoughts = "\n".join(p.text for p in event_parts if getattr(p, "thought", False))
                if thoughts:
                    await websocket.send_json({
                        "source": "assistant", "type": "ThoughtMessage", 
                        "content": thoughts, "m_id": response_m_id, "ts": datetime.now(timezone.utc).isoformat()
                    })

                # Stream Standard Text Chunks
                if getattr(event, "content", None):
                    text_chunk = "".join(p.text for p in event_parts if p.text and not getattr(p, "thought", False))
                    if text_chunk and getattr(event, 'partial', False):
                        await websocket.send_json({
                            "source": "assistant", "type": "TextMessage",
                            "content": text_chunk, "m_id": response_m_id, "ts": datetime.now(timezone.utc).isoformat()
                        })

            # Signal the frontend that generation is complete
            await websocket.send_json({
                "source": "assistant", "type": "FinalMessage", 
                "m_id": response_m_id, "ts": datetime.now(timezone.utc).isoformat()
            })

        except asyncio.CancelledError:
            logger.info("Agent generation was successfully cancelled by the user.")
        except Exception as e:
            logger.error(f"Agent execution error: {e}")

    # 5. Main WebSocket Receive Loop
    try:
        while True:
            data = await websocket.receive_text()
            try:
                data_json = json.loads(data)
            except json.JSONDecodeError: continue

            m_id = data_json.get('m_id', str(uuid.uuid4()))
            msg_type = data_json.get('type')
            parts = []

            # Non-LLM Events
            if msg_type == 'session':
                continue
            
            if msg_type == 'feedback':
                await save_feedback() # Hook to your utils
                continue


            # LLM Triggering Events
            if msg_type == 'AudioMessage':
                await cancel_running_task(reason="User started speaking")
                # Handle audio processing/STT here in production
                continue

            if msg_type == 'WidgetEvent':
                await cancel_running_task(reason="User interacted with a widget")
                payload = data_json.get("widgetEvent", {}).get("payload", {})
                text_content = "\n".join(f"{k}: {v}" for k, v in payload.items()).strip()
                if text_content:
                    parts.append(types.Part(text=f"[User Submitted Form/Widget]:\n{text_content}"))

            if msg_type == 'TextMessage':
                await cancel_running_task(reason="User typed a message")
                
                text_content = data_json.get('content', '')
                if text_content.strip():
                    parts.append(types.Part(text=text_content))

                if 'attachment' in data_json:
                    att = data_json['attachment']
                    att_data = base64.b64decode(att['data'])
                    mime = att.get('type', 'application/octet-stream')

                    if mime.startswith('image/'):
                        parts.append(types.Part(inline_data=types.Blob(mime_type=mime, data=att_data)))
                    else:
                        extracted_text = await extract_text_from_attachment(BytesIO(att_data), mime)
                        parts.append(types.Part(text=f"\n[Attachment Content]: {extracted_text}"))

            if parts:
                current_ai_task = asyncio.create_task(process_agent_request(parts, m_id))

    except WebSocketDisconnect:
        logger.info(f"Session {session_id} disconnected.")
    finally:
        pass

if __name__ == "__main__":
	import uvicorn
	uvicorn.run(app, host="0.0.0.0", port=8000)