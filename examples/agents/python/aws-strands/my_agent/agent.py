import os
import httpx
from openai import AsyncOpenAI
from strands import Agent
from strands.models.openai import OpenAIModel
from strands.session.file_session_manager import FileSessionManager
from strands.tools import tool 
from dotenv import load_dotenv

# Import framework-agnostic UI tools
from zijus_tools import SendSlots, SendSlider

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

instructions = """You are 'Finny', a financial assistant for Zijus Bank. Your ONLY job is to guide users through a strict 4-step loan pre-approval process.
CRITICAL: You MUST use the provided tools to gather user input. DO NOT ask users to type their answers. If you need an answer, you MUST fire a tool.

--- THE 4-STEP WORKFLOW ---

STEP 1: Gathering the Loan Amount
- If the user asks about a loan, DO NOT reply with a text question like 'How much do you need?'
- You MUST immediately execute the `send_slider_tool` tool.
- Tool Arguments -> content: 'Desired Loan Amount', min_value: 1000, max_value: 50000, default_value: 10000.
- Say a brief greeting and wait for the tool response.

STEP 2: Gathering the Repayment Term
- Once you receive the loan amount from the slider, you MUST immediately execute the `send_slots_tool` tool to get the term.
- Tool Arguments -> slots: ['12 Months', '24 Months', '36 Months'].
- Say: 'Great, an X amount loan. How long would you like to take to pay it back?'

STEP 3: The Calculation & Officer Prompt
- Once you receive the term, calculate a mock estimated monthly payment.
- Show the payment calculation clearly using markdown.
- Then, ask if they want to speak to a loan officer, and you MUST use the `send_slots_tool` tool to get their answer.
- Tool Arguments -> slots: ['Yes', 'No'].

STEP 4: Booking the Appointment
- If they clicked 'Yes', you MUST use the `send_slots_tool` tool one final time.
- Tool Arguments -> slots: ['Tomorrow 10:00 AM', 'Tomorrow 2:00 PM', 'Next Monday 11:00 AM'].
- If they clicked 'No', politely end the conversation.

--- STRICT RULES ---
1. NEVER ask a question that requires the user to type a structured answer. Always fire a tool.
2. Only move to the next step AFTER receiving the tool response from the user.
3. Keep your text responses incredibly short (1-2 sentences max). Let the UI tools do the talking."""

# --- WRAP ZIJUS TOOLS FOR STRANDS ---
@tool
async def send_slots_tool(slots: list[str]) -> str:
    """Renders clickable choice buttons (slots) in the chat UI.
    
    Args:
        slots: A list of string options for the user to choose from.
    """
    await SendSlots(slots=slots)
    return "UI rendered successfully. Stop generating and wait for the user."

@tool
async def send_slider_tool(content: str, min_value: int, max_value: int, default_value: int) -> str:
    """Renders an interactive range slider in the chat UI.
    
    Args:
        content: The text/title displayed above the slider.
        min_value: The minimum allowed value.
        max_value: The maximum allowed value.
        default_value: The starting value of the slider.
    """
    await SendSlider(content=content, min_value=min_value, max_value=max_value, default_value=default_value)
    return "UI rendered successfully. Stop generating and wait for the user."
# ------------------------------------

def get_agent(session_id: str = "", user_id: str = "", http_client: httpx.AsyncClient = None) -> Agent: # type: ignore
    """
    Creates and returns an AWS Strands Agent configured with OpenAI.
    """
    
    # 1. Manually initialize the native OpenAI client using our safe HTTPX client
    # This completely bypasses the Strands wrapper's buggy initialization code!
    native_openai_client = AsyncOpenAI(
        api_key=OPENAI_API_KEY,
        http_client=http_client
    )

    # 2. Pass the fully constructed native client into Strands
    openai_model = OpenAIModel(
        client=native_openai_client, # Directly inject the initialized client
        model_id="gpt-5.4-mini", 
        params={
            "temperature": 0.2, 
            "max_completion_tokens": 1000 
        }
    )

    session_manager = FileSessionManager(
        session_id=session_id,
        storage_dir="./tmp/strands_sessions"
    )

    agent = Agent(
        name="Zijus Financial Assistant",
        model=openai_model,
        system_prompt=instructions,
        session_manager=session_manager,
        tools=[send_slots_tool, send_slider_tool] 
    )

    return agent