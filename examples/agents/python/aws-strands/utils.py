from datetime import datetime, timezone, timedelta
import jwt
from jwt import InvalidTokenError
import uuid
import os

from dotenv import load_dotenv
load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-default-secret-key")

async def generate_jwt(session_id=None):
	current_date = datetime.now(timezone.utc).strftime('%Y%m%d')
	payload = {
		"session_id": session_id or f"{current_date}-{uuid.uuid4()}",
		"exp": datetime.now(timezone.utc) + timedelta(hours=24)
	}
	return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

async def validate_jwt(token):
	try:
		payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
		return payload
	except InvalidTokenError:
		return None

async def save_feedback():
    # Placeholder function to save feedback
    pass

async def send_email():
    # Placeholder function to send email
    pass

async def extract_text_from_attachment():
    # Placeholder function to extract text from attachment
    return "Extracted text from attachment"