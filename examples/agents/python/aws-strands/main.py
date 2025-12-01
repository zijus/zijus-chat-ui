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

# --- Local Imports ---
from my_agent.agent import get_agent
from utils import generate_jwt, validate_jwt, extract_text_from_attachment, save_feedback, send_email

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO)
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

    await websocket.accept()
    token = new_token if new_token else token
    await websocket.send_json({"type": "session", "token": token})

    if not user_id:
        user_id = "anon"

    # 3. Initialize Strands Agent
    # The agent.py logic handles session_manager injection for history
    agent = get_agent(session_id=session_id, user_id=user_id)

    try:
        while True:
            # A. Receive User Message
            data = await websocket.receive_text()
            
            try:
                data_json = json.loads(data)
            except json.JSONDecodeError:
                continue

            if 'type' not in data_json:
                continue

            m_id = data_json.get('m_id', str(uuid.uuid4()))
            msg_type = data_json.get('type')
            response_m_id = str(uuid.uuid4())

            # B. Prepare Input Payload
            # By default, input is just the text string
            prompt_text = data_json.get('content', '')
            
            # If we have images, 'input_payload' will become a list of messages
            # If text only, 'input_payload' remains a string
            input_payload = prompt_text

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

            if msg_type == 'TextMessage':
                if 'attachment' in data_json:
                    att = data_json['attachment']
                    att_type = att.get('type', '')
                    
                    if att_type.startswith('image/'):
                        try:
                            # 1. Decode Base64 Image
                            image_bytes = base64.b64decode(att['data'])
                            
                            # 2. Extract Format (e.g. 'image/png' -> 'png')
                            # Strands expects 'png', 'jpeg', 'webp', or 'gif'
                            img_format = att_type.split('/')[-1]
                            
                            # 3. Construct Strands Multimodal Message Structure
                            # Ref: {"role": "user", "content": [{"image": ...}, {"text": ...}]}
                            input_payload = [
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "image": {
                                                "format": img_format,
                                                "source": {
                                                    "bytes": image_bytes
                                                }
                                            }
                                        },
                                        {
                                            "text": prompt_text
                                        }
                                    ]
                                }
                            ]
                            logger.info(f"Processed image attachment: {img_format}")
                            
                        except Exception as e:
                            logger.error(f"Image processing error: {e}")
                            await websocket.send_json({
                                "source": "assistant", 
                                "content": "Failed to process image attachment.", 
                                "type": "error"
                            })
                            continue
                            
                    else:
                        # Simple doc handling (append to text)
                        try:
                            att_data = base64.b64decode(att['data'])
                            # Placeholder for actual text extraction logic
                            # extracted_text = await extract_text_from_attachment(att_type, att_data) #Placeholder
                            
                            extracted_text = "[Document content placeholder]" 
                            
                            # If input_payload is already a list (unlikely here but good practice), handle accordingly
                            # For doc text, we usually just append to the string prompt
                            if isinstance(input_payload, str):
                                input_payload += f"\n\n[Attachment Content]:\n{extracted_text}"
                        except Exception:
                            pass

            # Skip empty inputs
            if not input_payload:
                continue

            # C. Run Strands Agent Stream
            try:
                # Use the Async Iterator pattern from Strands SDK
                # Pass input_payload (either a String or a List of Messages)
                async for event in agent.stream_async(input_payload):
                    
                    # 1. Text Generation Events ("data")
                    if "data" in event:
                        chunk_content = event["data"]
                        if chunk_content:
                            await websocket.send_json({
                                "source": "assistant",
                                "content": chunk_content,
                                "m_id": response_m_id,
                                "type": "TextMessage", 
                                "ts": datetime.now(timezone.utc).isoformat()
                            })

                    # # 2. Tool Usage Events ("current_tool_use")
                    # elif "current_tool_use" in event:
                    #     tool_info = event["current_tool_use"]
                    #     tool_name = tool_info.get("name", "Unknown Tool")
                    #     await websocket.send_json({
                    #         "source": "assistant",
                    #         "content": f"🔧 Using tool: {tool_name}",
                    #         "m_id": response_m_id,
                    #         "type": "TextMessage", # Display as system text
                    #         "ts": datetime.now(timezone.utc).isoformat()
                    #     })

                    # # 3. Reasoning Events (if model supports it)
                    # elif "reasoningText" in event:
                    #     # Optional: Stream reasoning steps to client
                    #     pass

                    # 4. Error/Stop Events
                    elif event.get("force_stop", False):
                        reason = event.get("force_stop_reason", "Unknown")
                        logger.warning(f"Agent forced stop: {reason}")

            except Exception as e:
                logger.error(f"Strands execution error: {e}")
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