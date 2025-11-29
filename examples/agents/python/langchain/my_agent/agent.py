from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages
from typing import TypedDict, List, Annotated, Union
from dotenv import load_dotenv

load_dotenv()

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

model = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0.1,
    streaming=True
)

def llm_node(state: AgentState):
    """Run LLM with full conversation history."""
    messages = state["messages"]
    response = model.invoke(messages)
    return {"messages": [response]} 

graph = StateGraph(AgentState)

graph.add_node("model", llm_node)
graph.set_entry_point("model")
graph.add_edge("model", END)

checkpointer = MemorySaver()
agent = graph.compile(checkpointer=checkpointer)

def build_message_payload(user_input: Union[str, dict]):
    """
    Creates the LangGraph input payload.
    Handles both simple text (str) and multimodal content (dict).
    """
    message_content = []

    if isinstance(user_input, str):
        # Case 1: Simple text message
        message_content = user_input
    
    elif isinstance(user_input, dict) and user_input.get("role") == "user" and "content" in user_input:
        # Case 2: Multimodal message (list of parts)
        for part in user_input["content"]:
            if part["type"] == "text":
                message_content.append({"type": "text", "text": part["text"]})
            
            elif part["type"] == "image":
                mime_type = part.get("mime_type", "image/jpeg")
                base64_data = part["base64"]
                
                # Create the data URI for the image
                image_url_data = f"data:{mime_type};base64,{base64_data}"
                
                message_content.append({
                    "type": "image_url",
                    "image_url": {"url": image_url_data}
                })
            else:
                # Pass through any other parts as-is
                message_content.append(part)
    else:
        raise ValueError("User input must be a string (text) or a dict with 'role':'user' and a 'content' list (multimodal).")

    return {
        "messages": [
            HumanMessage(content=message_content)
        ]
    }

root_agent = agent