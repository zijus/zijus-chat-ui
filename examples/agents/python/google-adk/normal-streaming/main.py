from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.sessions import InMemorySessionService
from google.genai import types
from my_agent.agent import root_agent

import os
import json
import asyncio
import uuid
import logging
import base64
from utils import generate_jwt, validate_jwt, save_feedback, send_email, extract_text_from_attachment
from io import BytesIO
from datetime import datetime, timezone

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

APP_NAME=os.getenv("APP_NAME", "ZijusExampleApp")
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
    sender_role = websocket.query_params.get("role", "user")
    session_id = websocket.query_params.get("session_id", "")
    medium = websocket.query_params.get("medium", 'text') or 'text'
    # Parse custom data
    custom_data_str = websocket.query_params.get("custom_data")
    try:
        custom_data = json.loads(custom_data_str) if custom_data_str else {}
    except json.JSONDecodeError:
        custom_data = {}

    language_id = websocket.query_params.get("language", 'EN_US')

    # Modify the logic to handle JWT validation and generation
    user_id = None
    payload = None
    new_token = None

    if token:
        payload = await validate_jwt(token)

    if payload:
        user_id = payload.get("user_id") #modify the generation logic to include user_id
        if not session_id:
            session_id = payload.get("session_id")
    
    if not session_id:
        current_date = datetime.now().strftime('%Y%m%d')
        session_id = f"{current_date}-{uuid.uuid4()}"
    
    if not payload or not payload.get("session_id"):
        new_token = await generate_jwt(session_id)
        # Update payload if we generated a new token
        payload = await validate_jwt(new_token)

    await websocket.accept()
    token = new_token if new_token else token
    await websocket.send_json({"type": "session", "token": token})
    # End of JWT handling

    if not user_id:
        user_id = "anon" # Default user_id if not provided in JWT


    # Using InMemory for ADK specific state, while using your DB for chat history/logging
    session_service = InMemorySessionService() 
    runner = Runner(
        app_name=APP_NAME,
        agent=root_agent, # type: ignore
        session_service=session_service
    )

    # Initialize ADK session
    adk_session = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    if not adk_session:
        adk_session = await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    # Determine Modality (Native Audio vs Text)
    model_name = getattr(root_agent, 'model', 'gemini-2.0-flash-exp') # Fallback if model not set

    is_native_audio = "native-audio" in model_name.lower()
    response_modalities = ["AUDIO"] if is_native_audio else ["TEXT"]

    run_config = RunConfig(
                streaming_mode=StreamingMode.SSE,  # <--- This enables text streaming for standard models
                response_modalities=response_modalities,      # Standard models only support TEXT here
    )

    try:
        while True:
            # Wait for User Message
            data = await websocket.receive_text()
            ts_incoming_message = datetime.now(timezone.utc).isoformat()
            
            try:
                data_json = json.loads(data)
            except: continue
            m_id = data_json.get('m_id', str(uuid.uuid4()))
            msg_type = data_json.get('type')
            
            # Build ADK Content Object
            parts = []
            user_log_content = ""

            if msg_type == 'TextMessage':
                # Handle Text/Attachments
                content_text = data_json.get('content', '')
                user_log_content = content_text
                
                # If attachment is image:
                if 'attachment' in data_json:
                    att = data_json['attachment']
                    if att['type'].startswith('image/'):
                        parts.append(types.Part(
                            inline_data=types.Blob(
                                mime_type=att['type'], 
                                data=base64.b64decode(att['data'])
                            )
                        ))
                        user_log_content += " [Image]"
                    else:
                        att_data = base64.b64decode(att['data'])
                        mime = att.get('type', 'application/octet-stream')
                        # If Doc -> Extract text
                        att_file = BytesIO(att_data)
                        extracted_text = await extract_text_from_attachment() # Placeholder function
                        content_text += f"\n[Attachment Content]: {extracted_text}"

                
                if content_text:
                    parts.append(types.Part(text=content_text))

            if not parts: continue

            # Execute Agent (Synchronous runner.run wrapped in thread)
            new_message = types.Content(role="user", parts=parts)
            response_m_id = str(uuid.uuid4())
            accumulated_response = ""
        
            try:
                # Iterate the generator returned by run_standard_adk
                async for event in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=new_message,
                    run_config=run_config
                ):
                    is_partial = getattr(event, 'partial', False)
                    
                    text_chunk = ""
                    
                    # Extract Text
                    if hasattr(event, 'content') and event.content:
                        for part in event.content.parts: #type: ignore
                            if part.text: 
                                text_chunk += part.text
                    
                    # Stream Chunk
                    if text_chunk:
                        if is_partial:
                            accumulated_response += text_chunk
                            await websocket.send_json({
                                "source": "assistant",
                                "name": event.author,
                                "content": text_chunk,
                                "m_id": response_m_id,
                                "type": "TextMessage",
                                "ts": datetime.now(timezone.utc).isoformat()
                            })
            
            except ValueError as ve:
                if "Session not found" in str(ve):
                    logger.warning("Session ended during stream")
                else: logger.error(f"Runner error: {ve}")
            except Exception as e:
                logger.error(f"Standard execution error: {e}")

            # 5. Finalize Turn
            if accumulated_response:
                final_msg = {
                    "source": "assistant",
                    "name": event.author,
                    "content": accumulated_response,
                    "m_id": response_m_id,
                    "ref_m_id": m_id,
                    "user_id": user_id,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "type": "TextMessage"
                }
                # Placeholder to log final_msg to your DB if needed


    except WebSocketDisconnect:
        pass
    finally:
        pass

if __name__ == "__main__":
	import uvicorn
	uvicorn.run(app, host="0.0.0.0", port=8000)