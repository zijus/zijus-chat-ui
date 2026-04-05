from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.sessions import InMemorySessionService
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.genai import types
from my_agent.agent import root_agent

import os
import json
import asyncio
import uuid
import logging
import base64
import time
from io import BytesIO
from datetime import datetime, timezone
from typing import Optional

from utils import generate_jwt, validate_jwt, save_feedback, extract_text_from_attachment
from zijus_tools import set_websocket_sender

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
templates = Jinja2Templates(directory="templates")

APP_NAME = os.getenv("APP_NAME", "ZijusBidiExample")
ZIJUS_JAVASCRIPT = "https://cdn.jsdelivr.net/gh/zijus/zijus-chat-ui@main/dist/zijus-webclient-v0.1.0.js"

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "agent_name": APP_NAME, 
        "zijus_config": os.getenv("ZIJUS_CONFIG_ENCODED", ""), 
        "zijus_javascript": ZIJUS_JAVASCRIPT
    })

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token", "")
    session_id = websocket.query_params.get("session_id", "")
    
    payload = await validate_jwt(token) if token else None
    user_id = payload.get("user_id", "anon") if payload else "anon"
    session_id = session_id or (payload.get("session_id") if payload else f"sess-{uuid.uuid4()}")
    
    new_token = await generate_jwt(session_id) if not payload else token
    await websocket.accept()

    async def sender(msg: dict):
        await websocket.send_json(msg)
    set_websocket_sender(sender)

    await websocket.send_json({"type": "session", "token": new_token})

    # Initialize ADK
    session_service = InMemorySessionService() 
    runner = Runner(app_name=APP_NAME, agent=root_agent, session_service=session_service)

    adk_session = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    if not adk_session:
        await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)

    # --- BIDI / REALTIME CONFIGURATION ---
    run_config = RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=[types.Modality.AUDIO], # Force native audio responses
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        session_resumption=types.SessionResumptionConfig(),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfigDict(voice_name="Kore") # type: ignore
            )
        )
    )

    live_request_queue = LiveRequestQueue()

    # --- 3-TIER STATE MACHINE (NORMAL -> PAUSED -> MUTED) ---
    session_state = {
        "audio_state": "NORMAL", 
        "pause_buffer": [],
        "playing_until": 0.0,
        "is_generating": False
    }

    async def route_bot_message(payload: dict, duration_s: float = 0.0):
        """Routes audio/text based on the 3-Tier State Machine to prevent audio overlap."""
        state = session_state["audio_state"]
        
        if state == "MUTED":
            return  # Drop completely (Barge-in successful)
            
        if duration_s > 0:
            loop_now = asyncio.get_running_loop().time()
            session_state["playing_until"] = max(loop_now, session_state["playing_until"]) + duration_s
            
        if state == "PAUSED":
            session_state["pause_buffer"].append(payload) # Soft pause (Hold in memory)
        else:
            try: await websocket.send_json(payload)
            except Exception: pass

    async def hard_interrupt(reason: str):
        """Immediately stops all bot audio output."""
        logger.info(f"Barge-in triggered: {reason}")
        session_state["audio_state"] = "MUTED"
        session_state["pause_buffer"].clear()
        session_state["playing_until"] = 0.0
        try: await websocket.send_json({"source": "assistant", "type": "InterruptMessage", "ts": datetime.now(timezone.utc).isoformat()})
        except Exception: pass

    # --- TASK 1: UPSTREAM (Client -> Agent) ---
    async def upstream_task():
        try:
            while True:
                data = await websocket.receive_text()
                try: data_json = json.loads(data)
                except Exception: continue

                msg_type = data_json.get('type')

                # 1. Handle Audio Inputs
                if msg_type == 'AudioMessage':
                    audio_b64 = data_json.get('data', '')
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        is_partial = data_json.get('partial_audio', True)
                        
                        # A. Full Audio Uploads (e.g., from a REST client or file upload)
                        if not is_partial:
                            await hard_interrupt(reason="Received full audio upload")
                            mime = data_json.get('mimeType', 'audio/pcm;rate=16000')
                            live_request_queue.send_content(types.Content(
                                parts=[types.Part(inline_data=types.Blob(mime_type=mime, data=audio_bytes))], role="user"
                            ))
                            continue

                        # B. Realtime Streaming Audio (WebRTC / Browser Mic)
                        # Push raw chunks directly to Google's Live API
                        live_request_queue.send_realtime(types.Blob(
                            mime_type=data_json.get('mimeType', 'audio/pcm;rate=16000'), 
                            data=audio_bytes
                        ))
                        # Note: In an enterprise app, local VAD (like Silero) would go here 
                        # to trigger Soft Pauses before Google's cloud VAD reacts.

                # 2. Handle Text Inputs
                elif msg_type == 'TextMessage':
                    content_text = data_json.get('content', '')
                    if content_text:
                        await hard_interrupt(reason="User typed text")
                        live_request_queue.send_content(types.Content(
                            parts=[types.Part(text=content_text)], role="user"
                        ))

                # 3. Handle Widget/Form Interactions
                elif msg_type == 'WidgetEvent':
                    payload = data_json.get("widgetEvent", {}).get("payload", {})
                    text_content = "\n".join(f"{k}: {v}" for k, v in payload.items()).strip()
                    if text_content:
                        await hard_interrupt(reason="User interacted with UI Widget")
                        live_request_queue.send_content(types.Content(
                            parts=[types.Part(text=f"[User Submitted Form/Widget]:\n{text_content}")], role="user"
                        ))

        except WebSocketDisconnect:
            logger.info(f"Client disconnected: {session_id}")
            raise 

    # --- TASK 2: DOWNSTREAM (Agent -> Client) ---
    async def downstream_task():
        try:
            current_input_id = str(uuid.uuid4())
            current_output_id = str(uuid.uuid4())
            acc_input = ""
            acc_output = ""
            logged_in_tx = False
            
            async for event in runner.run_live(user_id=user_id, session_id=session_id, live_request_queue=live_request_queue, run_config=run_config):
                if event is None: continue
                
                # 1. Cloud Interruption
                if getattr(event, 'interrupted', False):
                    if session_state["audio_state"] != "MUTED":
                        await hard_interrupt(reason="Cloud VAD Interruption")

                # 2. Input Transcription
                if getattr(event, 'input_transcription', None):
                    tx = event.input_transcription
                    # Safely extract text for Pylance
                    in_text = tx.text if tx else None 
                    
                    if in_text:
                        if not logged_in_tx:
                            logged_in_tx = True
                            try: await websocket.send_json({
                                "source": "user", "type": "TextMessage", "is_transcription": True,
                                "content": "🎤 ...", "m_id": current_input_id, "ts": datetime.now(timezone.utc).isoformat()
                            })
                            except Exception: pass
                            
                        raw_text = in_text.strip()
                        if len(raw_text) > len(acc_input):
                            acc_input = raw_text

                # 3. Output Processing
                # A. Output Transcription (Text)
                if hasattr(event, 'output_transcription') and event.output_transcription:
                    tx = event.output_transcription
                    out_text = tx.text # Grab the property
                    
                    # If out_text is a string and not empty
                    if out_text and not getattr(tx, "finished", False):
                        acc_output += out_text
                        await route_bot_message({
                            "source": "assistant", "type": "TextMessage", "is_transcription": True,
                            "content": out_text, "m_id": current_output_id, "ts": datetime.now(timezone.utc).isoformat()
                        })

                # B. Output Audio Binary
                if hasattr(event, 'content') and event.content:
                    session_state["is_generating"] = True
                    
                    # Safely default to an empty list if parts is None
                    parts = event.content.parts or []
                    
                    for part in parts:
                        if hasattr(part, 'thought') and part.thought: continue
                        if hasattr(part, 'inline_data') and part.inline_data:
                            audio_chunk = part.inline_data.data
                            if audio_chunk: # Ensure it has data
                                await route_bot_message({
                                    "source": "assistant", "type": "AudioMessage",
                                    "data": base64.b64encode(audio_chunk).decode('utf-8'),
                                    "mime_type": part.inline_data.mime_type, "m_id": current_output_id,
                                    "ts": datetime.now(timezone.utc).isoformat()
                                }, duration_s=len(audio_chunk) / (24000 * 2))

                # 4. Turn Complete / Finalize Output
                if getattr(event, 'turn_complete', False):
                    session_state["is_generating"] = False
                        
                    # Flush User Text Final to UI
                    if acc_input.strip():
                        try: await websocket.send_json({
                            "source": "user", "type": "TextMessage", "is_transcription": True,
                            "content": acc_input.strip(), "m_id": current_input_id, "ts": datetime.now(timezone.utc).isoformat()
                        })
                        except Exception: pass
                    
                    # Signal bot completion
                    try: await websocket.send_json({"source": "assistant", "type": "FinalMessage", "m_id": current_output_id, "ts": datetime.now(timezone.utc).isoformat()})
                    except Exception: pass
                    
                    # Reset Session States
                    acc_input = ""
                    acc_output = ""
                    logged_in_tx = False
                    current_input_id = str(uuid.uuid4())
                    current_output_id = str(uuid.uuid4())
                    
                    session_state["audio_state"] = "NORMAL"
                    session_state["pause_buffer"].clear()

        except Exception as e:
            if "1011" in str(e) or "Internal error" in str(e):
                logger.info("Google Live API sent a known 1011 disconnect. Connection closed safely.")
            else:
                logger.error(f"Downstream error: {e}")
            raise

    # --- EXECUTE CONCURRENT TASKS ---
    try:
        done, pending = await asyncio.wait(
            [asyncio.create_task(upstream_task()), asyncio.create_task(downstream_task())],
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending: task.cancel()
        for task in done:
            try: task.result()
            except Exception: pass
    finally:
        live_request_queue.close()


if __name__ == "__main__":
	import uvicorn
	uvicorn.run(app, host="0.0.0.0", port=8000)