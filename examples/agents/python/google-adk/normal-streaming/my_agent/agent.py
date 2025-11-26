from google.adk.agents import LlmAgent
import os

agent = LlmAgent(
    name="root_agent",
    model="gemini-2.5-flash",
    description="A helpful AI assistant.",
    instruction="You are an AI Assistant"
)

root_agent = agent