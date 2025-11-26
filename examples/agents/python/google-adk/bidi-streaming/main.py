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
app.mount("/static", StaticFiles(directory="static"), name="static")

APP_NAME=os.getenv("APP_NAME", "ZijusExampleApp")

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

    voice_config = types.VoiceConfig(
        prebuilt_voice_config=types.PrebuiltVoiceConfigDict(
            voice_name="Kore" #change as needed
        ) # type: ignore
    )
    speech_config = types.SpeechConfig(voice_config=voice_config)
    run_config = RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=response_modalities,
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        session_resumption=types.SessionResumptionConfig(),
        speech_config=speech_config
    )

    live_request_queue = LiveRequestQueue()

    async def upstream_task():
        """Handles messages FROM User (WebSocket) -> Queue/Process"""
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
                    await save_feedback() # Placeholder function
                    continue

                if msg_type == 'send_email':
                    try:
                        email_body = base64.b64decode(data_json.get("email_body")).decode("utf-8")
                        await send_email() # Placeholder function
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
                            
                            # 3. Create Blob
                            audio_blob = types.Blob(
                                mime_type=mime_type, 
                                data=audio_bytes
                            )
                            
                            # 4. Send to ADK
                            live_request_queue.send_realtime(audio_blob)
                            
                    except Exception as e:
                        logger.error(f"Error processing AudioMessage: {e}")
                    
                    continue
                
                # 1. URL Extraction
                content_text = data_json.get('content', '')

                # 2. Prepare ADK Request parts
                parts = []
                
                # Handle Attachments
                if 'attachment' in data_json:
                    att = data_json['attachment']
                    try:
                        att_data = base64.b64decode(att['data'])
                        mime = att.get('type', 'application/octet-stream')
                        
                        # If Image -> Send as Blob
                        if mime.startswith('image/'):
                            image_blob = types.Blob(mime_type=mime, data=att_data)
                            live_request_queue.send_realtime(image_blob)
                            sent_to_adk = True
                            content_text += " [Image Attached]"
                        else:
                            # If Doc -> Extract text
                            att_file = BytesIO(att_data)
                            extracted_text = await extract_text_from_attachment() # Placeholder function
                            content_text += f"\n[Attachment Content]: {extracted_text}"
                    except Exception as e:
                        logger.error(f"Attachment error: {e}")

                # 3. Send Text to Queue
                if content_text:
                    content_part = types.Part(text=content_text)
                    content = types.Content(parts=[content_part], role="user")
                    live_request_queue.send_content(content)

                # E. Broadcast & Log User Message
                if msg_type != 'AudioMessage':
                    user_msg_obj = {
                        "source": "user",
                        "content": data_json.get('content', '') + (' [File Attached]' if 'attachment' in data_json else ''),
                        "m_id": m_id,
                        "ts": ts_incoming_message,
                        "user_id": user_id,
                        "type": "TextMessage"
                    }
                    
        except WebSocketDisconnect:
            logger.info("Upstream: Client disconnected")
        except Exception as e:
            logger.error(f"Error in upstream_task: {e}")

    async def downstream_task():
            """Handles events FROM Agent (ADK) -> User (WebSocket)"""
            try:
                current_response_id = str(uuid.uuid4())
                accumulated_text = ""
                # Helper to check if a part is an internal thought
                def is_thought(part):
                    return getattr(part, 'thought', False)

                async for event in runner.run_live(
                    user_id=user_id,
                    session_id=session_id,
                    live_request_queue=live_request_queue,
                    run_config=run_config
                ):
                    if event.input_transcription:
                        transcription = getattr(event.input_transcription, 'text', None)
                        if transcription:
                            accumulated_text += transcription
                            chunk_msg = {
                                "source": "user",
                                "content": transcription,
                                "m_id": current_response_id,
                                "type": "TextMessage",
                                "ts": datetime.now(timezone.utc).isoformat()
                            }
                            await websocket.send_json(chunk_msg)

                    if is_native_audio:
                        # 1. Handle Text Transcription (Overlay)
                        if hasattr(event, 'output_transcription') and event.output_transcription:
                            # Depending on ADK version, this might be event.output_transcription.text or similar
                            # Adjust based on the actual object structure, assuming .text based on your JSON
                            transcription = getattr(event.output_transcription, 'text', None)
                            if transcription:
                                accumulated_text += transcription
                                chunk_msg = {
                                    "source": "assistant",
                                    "name": event.author,
                                    "content": transcription,
                                    "m_id": current_response_id,
                                    "type": "TextMessage",
                                    "ts": datetime.now(timezone.utc).isoformat()
                                }
                                await websocket.send_json(chunk_msg)

                        # 2. Handle Audio Binary Data
                        if hasattr(event, 'content') and event.content:
                            for part in event.content.parts: #type: ignore
                                if is_thought(part): continue # Skip thoughts

                                # Check for inline data (audio bytes)
                                if hasattr(part, 'inline_data') and part.inline_data:
                                    audio_bytes = part.inline_data.data # This usually comes as bytes
                                    mime_type = part.inline_data.mime_type
                                    
                                    # Send audio chunk to client
                                    b64_audio = base64.b64encode(audio_bytes).decode('utf-8') # type: ignore
                                    audio_msg = {
                                        "source": "assistant",
                                        "name": event.author,
                                        "data": b64_audio,
                                        "mime_type": mime_type,
                                        "m_id": current_response_id,
                                        "type": "AudioMessage",
                                        "ts": datetime.now(timezone.utc).isoformat()
                                    }
                                    await websocket.send_json(audio_msg)

                        # 3. Handle End of Turn (Completion or Interruption)
                        is_interrupted = getattr(event, 'interrupted', False)
                        
                        if event.turn_complete or is_interrupted:
                            if is_interrupted:
                                accumulated_text += "* ⏸️ Interrupted*"
                                interruption_msg = {
                                    "source": "assistant",
                                    "name": event.author,
                                    "content": "* ⏸️ Interrupted*",
                                    "m_id": current_response_id,
                                    "type": "TextMessage", 
                                    "ts": datetime.now(timezone.utc).isoformat()
                                }
                                await websocket.send_json(interruption_msg)
                            # Finalize the transaction in DB
                            final_msg = {
                                "source": "assistant",
                                "name": event.author,
                                "content": accumulated_text, # Save the full text transcript
                                "m_id": current_response_id,
                                "user_id": user_id,
                                "ts": datetime.now(timezone.utc).isoformat(),
                                "type": "TextMessage" # We save as text for history readability
                            }
                            
                            # Reset for next turn
                            current_response_id = str(uuid.uuid4())
                            accumulated_text = ""

                    else:
                        #print("Processing Standard Text Event:", event)
                        is_partial = getattr(event, 'partial', False)
                        
                        # 1. Handle Content
                        if hasattr(event, 'content') and event.content:
                            text_chunk_for_this_event = ""
                            
                            for part in event.content.parts: #type: ignore
                                if is_thought(part): continue # Skip thoughts
                                if part.text:
                                    text_chunk_for_this_event += part.text

                            if text_chunk_for_this_event:
                                # If Partial: Send to client AND accumulate
                                if is_partial:
                                    accumulated_text += text_chunk_for_this_event
                                    chunk_msg = {
                                        "source": "assistant",
                                        "name": event.author,
                                        "content": text_chunk_for_this_event,
                                        "m_id": current_response_id,
                                        "type": "TextMessage",
                                        "ts": datetime.now(timezone.utc).isoformat()
                                    }
                                    await websocket.send_json(chunk_msg)
                                
                                pass

                        # 2. Handle End of Turn (turnComplete)
                        if event.turn_complete:
                            final_msg = {
                                "source": "assistant",
                                "name": event.author,
                                "content": accumulated_text,
                                "m_id": current_response_id,
                                "user_id": user_id,
                                "ts": datetime.now(timezone.utc).isoformat(),
                                "type": "TextMessage"
                            }
                            # Placeholder for processing final_msg if needed
                            
                            # Reset
                            current_response_id = str(uuid.uuid4())
                            accumulated_text = ""

            except Exception as e:
                logger.error(f"Error in downstream_task: {e}")
                import traceback
                traceback.print_exc()
            finally:
                pass

    try:
        # Run Upstream, Downstream, and Redis Listener concurrently
        await asyncio.gather(
            upstream_task(),
            downstream_task()
        )
    except Exception as e:
        logger.error(f"Session loop terminated: {e}")
    finally:
        # Cleanup
        live_request_queue.close()
        try:
            await websocket.close()
        except:
            pass
