import os
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
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

# --- WRAP ZIJUS TOOLS ---
async def send_slots_tool(slots: list[str]) -> str:
    """Renders clickable choice buttons (slots) in the chat UI."""
    await SendSlots(slots=slots)
    return "UI rendered successfully. Stop generating and wait for the user."

async def send_slider_tool(content: str, min_value: int, max_value: int, default_value: int) -> str:
    """Renders an interactive range slider in the chat UI."""
    await SendSlider(content=content, min_value=min_value, max_value=max_value, default_value=default_value)
    return "UI rendered successfully. Stop generating and wait for the user."
# ------------------------


class AgentManager:
    """Manages isolated AutoGen AssistantAgents per WebSocket session."""
    def __init__(self):
        self.agents = {}
        self.model_client = OpenAIChatCompletionClient(
            model="gpt-5.4-mini",
            api_key=OPENAI_API_KEY
        )

    def get_agent(self, session_id: str) -> AssistantAgent:
        if session_id not in self.agents:
            self.agents[session_id] = AssistantAgent(
                name="Finny",
                model_client=self.model_client,
                system_message=instructions,
                tools=[send_slots_tool, send_slider_tool],
                model_client_stream=True, # Crucial for the typewriter effect!
            )
        return self.agents[session_id]

# Export a global instance
agent_manager = AgentManager()