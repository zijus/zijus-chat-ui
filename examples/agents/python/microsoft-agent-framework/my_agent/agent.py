from agent_framework.openai import OpenAIResponsesClient
from agent_framework import ChatMessage, TextContent
from dotenv import load_dotenv
import json

load_dotenv()

class RootAgent:
    def __init__(self):
        self.chat_client = OpenAIResponsesClient(model_id="gpt-4.1-mini")
        self.instructions = "You are a helpful AI assistant."
        self.agent = None
        self.conversation_histories = {}  # Manual conversation history by session_id
    
    async def initialize_agent(self):
        """Initialize the chat agent once"""
        if self.agent is None:
            self.agent = self.chat_client.create_agent(
                name="VisionAssistant",
                instructions=self.instructions,
            )
    
    def get_conversation_history(self, session_id):
        """Get or create conversation history for the session"""
        if session_id not in self.conversation_histories:
            self.conversation_histories[session_id] = []
        return self.conversation_histories[session_id]
    
    async def run_stream(self, task, session_id="default"):
        """Run the agent with streaming response using manual context"""
        await self.initialize_agent()
        history = self.get_conversation_history(session_id)
        
        # Build messages with full history
        messages = []
        
        # Add system message
        messages.append(ChatMessage(
            role="system",
            contents=[TextContent(text=self.instructions)]
        ))
        
        # Add conversation history
        for msg in history:
            messages.append(msg)
        
        # Add current message
        messages.append(task)
        
        # Run the agent
        async for chunk in self.agent.run_stream(messages): #type: ignore
            yield chunk
        
        # Store the new message in history
        history.append(task)
        
        # Also store the assistant's response (we'd need to capture it)
        # This would require more complex handling to capture the full response
    
    async def close(self):
        """Clean up the agent"""
        pass

# Create a global agent instance
root_agent = RootAgent()