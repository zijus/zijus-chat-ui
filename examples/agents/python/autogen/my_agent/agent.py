import asyncio
from autogen_agentchat.agents import AssistantAgent
#from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import ChatCompletionClient

from dotenv import load_dotenv
load_dotenv()

model_config = {
    'provider': 'autogen_ext.models.openai.OpenAIChatCompletionClient', 
    'component_type': 'model',
    'version': 1,
    'component_version': 1,
    'config': 
        {
            'model': "gpt-4.1", 
            'max_tokens': 1000,
            'temperature': 0.1,
            'stream_options': {"include_usage": True},
            'model_info': {
                "multiple_system_messages": True,
                "vision": True,
                "function_calling": True,
                "json_output": True,
                "family": "unknown",
                "structured_output": True,
            }
        }
}

model_client = ChatCompletionClient.load_component(model_config)

agent = AssistantAgent(
    name="assistant",
    model_client=model_client,
    model_client_stream=True,
    system_message="You are a helpful AI assistant."
)

root_agent = agent