import os
import json
import base64
import logging
import uuid
from io import BytesIO
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# --- Agno Imports ---
from agno.media import Image as AgnoImage
from my_agent.agent import root_agent

# --- Utilities ---
from utils import generate_jwt, validate_jwt, extract_text_from_attachment, save_feedback, send_email

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    
    # 2. JWT & Session Handling
    user_id = None
    payload = None
    new_token = None

    if token:
        payload = await validate_jwt(token)

    if payload:
        user_id = payload.get("user_id")
        if not session_id:
            session_id = payload.get("session_id")
    
    if not session_id:
        current_date = datetime.now().strftime('%Y%m%d')
        session_id = f"{current_date}-{uuid.uuid4()}"
    
    if not payload or not payload.get("session_id"):
        new_token = await generate_jwt(session_id)
        # Update payload if we generated a new token (simulated logic)
        # payload = await validate_jwt(new_token)

    await websocket.accept()
    token = new_token if new_token else token
    await websocket.send_json({"type": "session", "token": token})

    if not user_id:
        user_id = "anon"

    # 3. Initialize Agno Agent for this session
    # Agno manages history persistence via the storage defined in agent.py
    agent = root_agent

    try:
        while True:
            # A. Receive User Message
            data = await websocket.receive_text()
            
            try:
                data_json = json.loads(data)
            except json.JSONDecodeError:
                continue

            # Check for non-chat events (e.g. ping/pong or system events)
            if 'type' not in data_json:
                continue

            m_id = data_json.get('m_id', str(uuid.uuid4()))
            msg_type = data_json.get('type')
            response_m_id = str(uuid.uuid4())

            # B. Prepare Inputs for Agno
            prompt_text = data_json.get('content', '')
            images = []

            if msg_type == 'session':
                continue
            
            if msg_type == 'feedback':
                await save_feedback() # Placeholder 
                continue

            if msg_type == 'send_email':
                try:
                    email_body = base64.b64decode(data_json.get("email_body")).decode("utf-8")
                    await send_email() # Placeholder
                except Exception as e:
                    logger.error(f"Email error: {e}")
                continue

            if msg_type == 'AudioMessage':
                try:
                    # 1. Decode Base64
                    audio_b64 = data_json.get('data', '')
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        
                        # 2. Get Mime Type (default to 16k if missing)
                        mime_type = data_json.get('mimeType', 'audio/pcm;rate=16000')
                        
                        logger.info(f"Audio message received: {len(audio_bytes)} bytes, mime: {mime_type}")
                        
                except Exception as e:
                    logger.error(f"Error processing AudioMessage: {e}")
                
                continue


            if msg_type == 'TextMessage':
                # Handle Attachments
                if 'attachment' in data_json:
                    att = data_json['attachment']
                    att_type = att.get('type', '')
                    
                    if att_type.startswith('image/'):
                        # --- Image Handling ---
                        # Agno accepts images as base64 strings directly in AgnoImage
                        try:
                            # Use Agno's Image class
                            img = AgnoImage(
                                content=base64.b64decode(att['data']),
                                format=att_type.split('/')[-1] # e.g., 'png' or 'jpeg'
                            )
                            images.append(img)
                            logger.info("Image attachment processed")
                        except Exception as e:
                            logger.error(f"Image processing error: {e}")
                            await websocket.send_json({
                                "source": "assistant",
                                "content": "Error processing image attachment.",
                                "type": "error"
                            })
                            continue
                    else:
                        try:
                            att_data = base64.b64decode(att['data'])
                            # Placeholder for your extract function
                            # extracted_text = await extract_text_from_attachment(BytesIO(att_data)) 
                            extracted_text = "[Document content extracted]" 
                            prompt_text += f"\n\n[Attachment Content]:\n{extracted_text}"
                        except Exception as e:
                            logger.error(f"Doc processing error: {e}")

            # If no content, skip
            if not prompt_text and not images:
                continue

            # C. Run Agno Agent Stream
            try:
                run_response = agent.arun(
                    prompt_text,
                    images=images,
                    stream=True
                )

                async for chunk in run_response:
                    # chunk is a RunResponse object. 
                    # chunk.content contains the delta text in streaming mode.
                    if chunk.content:
                        await websocket.send_json({
                            "source": "assistant",
                            "content": chunk.content,
                            "m_id": response_m_id,
                            "type": "TextMessage", 
                            "ts": datetime.now(timezone.utc).isoformat()
                        })
                

            except Exception as e:
                logger.error(f"Agno execution error: {e}")
                await websocket.send_json({
                    "source": "assistant", 
                    "content": f"An error occurred: {str(e)}", 
                    "type": "error"
                })

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")
    finally:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)