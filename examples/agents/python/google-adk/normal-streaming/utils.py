from datetime import datetime, timezone, timedelta
import jwt
from jwt.exceptions import InvalidTokenError
import uuid
import os
from io import BytesIO
from typing import Optional, Dict, Any

from dotenv import load_dotenv
load_dotenv()

# Force Pylance to recognize this as a strict string
SECRET_KEY: str = str(os.getenv("JWT_SECRET_KEY", "your-default-secret-key-please-change"))

async def generate_jwt(session_id: Optional[str] = None) -> str:
    """Generates a secure JWT for the WebSocket session."""
    current_date = datetime.now(timezone.utc).strftime('%Y%m%d')
    payload = {
        "session_id": session_id or f"{current_date}-{uuid.uuid4()}",
        "exp": datetime.now(timezone.utc) + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

async def validate_jwt(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Validates the JWT and returns the payload if successful."""
    # This prevents the "UnionType" error by guaranteeing token is a string below
    if not token:
        return None 
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except InvalidTokenError:
        return None

async def extract_text_from_attachment(file_obj: BytesIO, mime_type: Optional[str]) -> str:
    """Placeholder function to extract text from documents."""
    if mime_type in ["text/plain", "text/csv"]:
        try:
            return file_obj.read().decode("utf-8", errors="ignore")
        except Exception:
            pass

    return f"[Simulated text extraction for file of type {mime_type}]"

async def save_feedback() -> None: 
    """ Placeholder function to save user feedback (thumbs up/down). Connect this to your database (PostgreSQL, MongoDB, etc.) """
    pass

