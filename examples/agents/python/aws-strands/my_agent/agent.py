import os
from strands import Agent
from strands.models.gemini import GeminiModel
from strands.session.file_session_manager import FileSessionManager
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY") # Ensure this is set in your .env

def get_agent(session_id: str = None, user_id: str = None) -> Agent:
    """
    Creates and returns an AWS Strands Agent configured with Google Gemini.
    """
    
    # 1. Initialize the Model
    gemini_model = GeminiModel(
        client_args={
            "api_key": GEMINI_API_KEY,
        },
        model_id="gemini-2.5-flash", 
        params={
            "temperature": 0.7,
            "max_output_tokens": 1000
        }
    )

    # 2. Initialize Session Manager
    session_manager = FileSessionManager(
        session_id=session_id,
        storage_dir="./tmp/strands_sessions"
    )
    # 2. Initialize the Agent
    # You can add tools here via the `tools=[...]` parameter if defined
    agent = Agent(
        name="agent",
        model=gemini_model,
        system_prompt="You are a helpful AI assistant. Answer concisely and clearly.",
        session_manager=session_manager,
    )

    return agent