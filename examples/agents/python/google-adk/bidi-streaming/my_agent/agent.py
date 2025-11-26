from google.adk.agents import LlmAgent
import os

agent = LlmAgent(
    name="root_agent",
    model=os.getenv("AGENT_MODEL", "gemini-2.5-flash"),
    description="A helpful AI assistant.",
    instruction="You are an AI Assistant"
)

root_agent = agent