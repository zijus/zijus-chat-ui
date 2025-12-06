from google.adk.agents import LlmAgent
import os

agent = LlmAgent(
    name="root_agent",
    model="gemini-2.5-flash-native-audio-preview-09-2025", #Use gemini-2.5-flash-native-audio-preview-09-2025 for Audio
    description="A helpful AI assistant.",
    instruction="You are an AI Assistant"
)

root_agent = agent