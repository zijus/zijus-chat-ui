from google.adk.agents import LlmAgent
from google.adk.planners import BuiltInPlanner
from google.genai import types
from zijus_tools import SendSlots, SendSlider, SendDatePicker

agent = LlmAgent(
    name="root_agent",
    tools=[SendSlots, SendSlider, SendDatePicker],
    model="gemini-2.5-flash",
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=False,
            thinking_budget=256,
        )
    ),
    description="A helpful AI assistant.",
    instruction="""Use SendSlots when you need to ask the user for text input. 
    Use SendDatePicker when you need to ask the user for a date input. 
    Use SendSlider when you need to ask the user for a number input. 
    """,
)


root_agent = agent