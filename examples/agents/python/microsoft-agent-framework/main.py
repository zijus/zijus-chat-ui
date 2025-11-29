from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agent_framework import ChatMessage, TextContent, DataContent
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

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

# Import the agent
from my_agent.agent import root_agent

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    logger.info("Starting up FastAPI application...")
    yield
    # Shutdown code
    logger.info("Shutting down FastAPI application...")
    await root_agent.close()

app = FastAPI(lifespan=lifespan)

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

def extract_text_from_chunk(chunk):
    """Safely extract text content from various chunk types"""
    # Try direct text attribute first
    if hasattr(chunk, 'text') and chunk.text:
        return chunk.text
    
    # Try content attribute
    if hasattr(chunk, 'content'):
        content = chunk.content
        # If content has text attribute
        if hasattr(content, 'text') and content.text:
            return content.text
        # If content is a string
        elif isinstance(content, str):
            return content
    
    # Try delta attribute (but check structure first)
    if hasattr(chunk, 'delta'):
        delta = chunk.delta
        # Check if delta has text attribute
        if hasattr(delta, 'text') and delta.text:
            return delta.text
        # Check if delta has content that might contain text
        elif hasattr(delta, 'content'):
            content = delta.content
            if hasattr(content, 'text') and content.text:
                return content.text
    
    # Final fallback - string representation
    try:
        chunk_str = str(chunk)
        if chunk_str and chunk_str not in ['', 'None']:
            return chunk_str
    except:
        pass
    
    return None

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

    try:
        while True:
            data = await websocket.receive_text()
            ts_incoming_message = datetime.now(timezone.utc).isoformat()

            try:
                data_json = json.loads(data)
            except json.JSONDecodeError:
                continue

            m_id = data_json.get('m_id', str(uuid.uuid4()))
            msg_type = data_json.get('type')

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
            
            content_text = data_json.get('content', '')

            # Prepare message parts for agent
            contents = []
            
            # Handle Attachments
            if 'attachment' in data_json:
                att = data_json['attachment']
                try:
                    att_data = base64.b64decode(att['data'])
                    mime = att.get('type', 'application/octet-stream')
                    print(f"Attachment received: {mime}, size: {len(att_data)} bytes")
                    # If Image -> Use DataContent
                    if mime.startswith('image/'):
                        contents.append(DataContent(
                            data=att_data,
                            media_type=mime
                        ))
                        logger.info(f"Processing image attachment: {mime}, size: {len(att_data)} bytes")
                    else:
                        # If Doc -> Extract text
                        att_file = BytesIO(att_data)
                        extracted_text = await extract_text_from_attachment() # Placeholder function
                        content_text += f"\n[Attachment Content]: {extracted_text}"
                except Exception as e:
                    logger.error(f"Attachment error: {e}")
                

            # Add text content if provided
            if content_text:
                contents.append(TextContent(text=content_text))

            if not contents:
                continue

            # C. Run Agent with Streaming - USING PERSISTENT THREAD FOR SESSION
            response_m_id = str(uuid.uuid4())
            
            try:
                # Create the chat message
                chat_message = ChatMessage(
                    role="user",
                    contents=contents
                )
                
                # Use the imported root_agent with session_id to maintain conversation context
                logger.info(f"Running agent for session: {session_id}")
                async for chunk in root_agent.run_stream(chat_message, session_id=session_id):
                    # Use the safe text extraction function
                    text_content = extract_text_from_chunk(chunk)
                    
                    if text_content:
                        await websocket.send_json({
                            "source": "assistant",
                            "content": text_content,
                            "m_id": response_m_id,
                            "type": "TextMessage", 
                            "ts": datetime.now(timezone.utc).isoformat()
                        })

            except Exception as e:
                logger.error(f"Agent execution error: {e}")
                await websocket.send_json({
                    "source": "assistant", 
                    "content": "An error occurred while processing your request.", 
                    "type": "error"
                })

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")
    finally:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)