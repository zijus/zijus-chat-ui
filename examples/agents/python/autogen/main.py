from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from my_agent.agent import root_agent
from autogen_agentchat.messages import (
    MultiModalMessage, 
    TextMessage, 
    ToolCallSummaryMessage, 
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

    try:
        while True:
            # A. Receive User Message
            data = await websocket.receive_text()
            ts_incoming = datetime.now(timezone.utc).isoformat()
            
            try:
                data_json = json.loads(data)
            except json.JSONDecodeError:
                continue

            m_id = data_json.get('m_id', str(uuid.uuid4()))
            msg_type = data_json.get('type')

            # B. Build AutoGen Request Message
            request_message = None
            content_text = data_json.get('content', '')

            if msg_type == 'TextMessage':
                # 1. Handle Attachments (Images or Docs)
                if 'attachment' in data_json:
                    att = data_json['attachment']
                    att_data = base64.b64decode(att['data'])
                    
                    if att['type'].startswith('image/'):
                        # --- Image Handling (MultiModal) ---
                        try:
                            pil_image = Image.open(BytesIO(att_data))
                            ag_image = AGImage(pil_image)
                            # AutoGen expects a list for MultiModal content
                            request_message = MultiModalMessage(
                                content=[content_text, ag_image],
                                source="user"
                            )
                        except Exception as e:
                            logger.error(f"Image processing error: {e}")
                            await websocket.send_json({
                                "source": "assistant",
                                "content": "Error processing image attachment.",
                                "type": "TextMessage"
                            })
                            continue
                    else:
                        # --- Document Handling (Extract Text) ---
                        # extracted_text = await extract_text_from_attachment(BytesIO(att_data)) 
                        extracted_text = "[Document content placeholder]" # Replace with actual extraction
                        content_text += f"\n[Attachment Content]: {extracted_text}"
                        
                        request_message = TextMessage(
                            content=content_text,
                            source="user"
                        )
                else:
                    # --- Plain Text Handling ---
                    if content_text:
                        request_message = TextMessage(
                            content=content_text,
                            source="user"
                        )

            if not request_message:
                continue

            # C. Run AutoGen Agent
            response_m_id = str(uuid.uuid4())
            
            try:
                # Run the stream using the AutoGen root_agent
                stream = root_agent.run_stream(task=request_message)

                async for message in stream:
                    # 1. Handle Final Task Result (Skip or Log)
                    if isinstance(message, TaskResult):
                        continue

                    # 2. Handle Streaming Chunks (The "Typewriter" effect)
                    # Note: Ensure your agent is initialized with model_client_stream=True
                    if isinstance(message, ModelClientStreamingChunkEvent):
                        chunk_content = message.content
                        if chunk_content:
                            await websocket.send_json({
                                "source": "assistant",
                                "content": chunk_content,
                                "m_id": response_m_id,
                                "type": "TextMessage", 
                                "ts": datetime.now(timezone.utc).isoformat()
                            })

                    # 3. Handle Full Text Messages (Final Answer or Internal Steps)
                    elif isinstance(message, TextMessage):
                        # In streaming mode, you usually rely on Chunks for the UI, 
                        # but you might want to log this or send a 'final' signal.
                        # For this example, we verify if we need to send it.
                        pass 

                    # 4. Handle Tool Calls (Optional)
                    # elif isinstance(message, ToolCallSummaryMessage):
                    #     await websocket.send_json({
                    #         "source": "assistant",
                    #         "content": f"🛠️ Executing tool: {message.content}",
                    #         "m_id": response_m_id,
                    #         "type": "TextMessage", # Display tool usage as text
                    #         "ts": datetime.now(timezone.utc).isoformat()
                    #     })

            except Exception as e:
                logger.error(f"AutoGen execution error: {e}")
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