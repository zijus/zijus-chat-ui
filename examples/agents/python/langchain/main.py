from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import os
import json
import uuid
import logging
import base64
from io import BytesIO
from datetime import datetime, timezone

from my_agent.agent import root_agent, build_message_payload

from utils import generate_jwt, validate_jwt, save_feedback, send_email, extract_text_from_attachment

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
    token = websocket.query_params.get("token", "")
    session_id = websocket.query_params.get("session_id", "")
    sender_role = websocket.query_params.get("role", "user")
    custom_data_str = websocket.query_params.get("custom_data")

    try:
        custom_data = json.loads(custom_data_str) if custom_data_str else {}
    except Exception:
        custom_data = {}

    user_id = None
    payload = None
    new_token = None

    if token:
        try:
            payload = await validate_jwt(token)
        except:
            payload = None

    if payload:
        user_id = payload.get("user_id")
        if not session_id:
            session_id = payload.get("session_id")

    # generate session_id if needed
    if not session_id:
        session_id = f"{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4()}"

    # generate token if needed
    if not payload or not payload.get("session_id"):
        new_token = await generate_jwt(session_id)
        try:
            payload = await validate_jwt(new_token)
        except:
            payload = None

    await websocket.accept()
    token = new_token if new_token else token

    # initial handshake back to UI
    await websocket.send_json({"type": "session", "token": token})

    if not user_id:
        user_id = "anon"

    # enable the 3 stream modes
    stream_modes = ["messages", "updates", "custom"]

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data_json = json.loads(raw)
            except:
                continue

            msg_type = data_json.get("type")
            content_text = data_json.get("content", "")
            m_id = data_json.get("m_id", str(uuid.uuid4()))

            # Ignore control messages
            if msg_type in ["session", None]:
                continue

            # Feedback
            if msg_type == "feedback":
                await save_feedback() #Placeholder
                continue

            # Email
            if msg_type == "send_email":
                try:
                    decoded = base64.b64decode(data_json.get("email_body")).decode("utf-8")
                    await send_email() #Placeholder
                except Exception as e:
                    logger.error(f"Email error: {e}")
                continue

            if msg_type == "TextMessage":
                if "attachment" in data_json:
                    att = data_json["attachment"]
                    raw_bytes = base64.b64decode(att["data"])
                    
                    # 1. Start building the multimodal content list
                    multimodal_content = []
                    
                    # 2. Add the text part (the user's descriptive prompt)
                    if content_text:
                        multimodal_content.append({"type": "text", "text": content_text})

                    if att["type"].startswith("image/"):
                        image_part = {
                            "type": "image",
                            "base64": att["data"], 
                            "mime_type": att["type"],
                        }
                        multimodal_content.append(image_part)
                        
                        # Update the entire user_input to the complex dict structure
                        user_input = {
                            "role": "user",
                            "content": multimodal_content
                        }
                        
                    else:
                        # Handle other document types (document, PDF, etc.)
                        #extracted = await extract_text_from_attachment() #Placeholder
                        extracted = "[Document content placeholder]"
                        user_input = f"{content_text}\n[Attachment Content]: {extracted}"

                elif content_text:
                    # If no attachment, the user_input remains the simple content_text string
                    user_input = content_text
                
            else:
                continue  # skip non-TextMessage types

            # build incremental payload (critical for memory)
            payload = build_message_payload(user_input)

            response_m_id = str(uuid.uuid4())

            thread_id = session_id
            config = {"configurable": {"thread_id": thread_id}}
            try:
                async for item in root_agent.astream(
                    payload,
                    stream_mode=stream_modes,
                    config=config
                ):
                    # Normalize tuple or non-tuple
                    if isinstance(item, tuple) and len(item) == 2:
                        smode, chunk = item
                    else:
                        smode = None
                        chunk = item

                    # CUSTOM STREAMING
                    if smode == "custom":
                        await websocket.send_json({
                            "source": "assistant",
                            "content": str(chunk),
                            "m_id": response_m_id,
                            "type": "TextMessage",
                            "stream_mode": "custom",
                            "ts": datetime.now(timezone.utc).isoformat()
                        })
                        continue

                    # TOKEN STREAMING
                    if smode == "messages":
                        text = getattr(chunk, "content", None)
                        if text:
                            await websocket.send_json({
                                "source": "assistant",
                                "content": text,
                                "m_id": response_m_id,
                                "type": "TextMessage",
                                "stream_mode": "messages",
                                "ts": datetime.now(timezone.utc).isoformat()
                            })
                        continue

                    # UPDATES — skip final model messages to prevent duplicates
                    if smode == "updates":
                        if isinstance(chunk, dict):
                            for step, data in chunk.items():
                                msgs = data.get("messages", [])
                                if msgs:
                                    for msg in msgs:
                                        text = getattr(msg, "content", "")
                                        if text:
                                            await websocket.send_json({
                                                "source": "assistant",
                                                "content": text,
                                                "m_id": response_m_id,
                                                "type": "TextMessage",
                                                "stream_mode": "updates",
                                                "step": step,
                                                "ts": datetime.now(timezone.utc).isoformat()
                                            })
                                else:
                                    await websocket.send_json({
                                        "source": "assistant",
                                        "content": str(data),
                                        "m_id": response_m_id,
                                        "type": "TextMessage",
                                        "stream_mode": "updates",
                                        "step": step,
                                        "ts": datetime.now(timezone.utc).isoformat()
                                    })
                        continue

                    # fallback
                    await websocket.send_json({
                        "source": "assistant",
                        "content": str(chunk),
                        "m_id": response_m_id,
                        "type": "TextMessage",
                        "stream_mode": smode or "unknown",
                        "ts": datetime.now(timezone.utc).isoformat()
                    })


            except Exception as e:
                logger.exception(f"LangGraph execution error: {e}")
                await websocket.send_json({
                    "source": "assistant",
                    "content": "An error occurred while processing your request.",
                    "type": "error"
                })

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: %s", session_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
