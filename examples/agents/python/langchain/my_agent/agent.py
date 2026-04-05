from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages
from typing import TypedDict, List, Annotated, Union
from dotenv import load_dotenv

# Import standard Zijus UI tools
from zijus_tools import SendSlots 

load_dotenv()

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

# 1. Initialize Model
llm = ChatOpenAI(
    model="gpt-4.1-mini", 
    temperature=0.1,
    streaming=True
)

# 2. Bind Zijus UI Tools NATIVELY to LangChain
# Because SendSlots is a standard Python function, LangChain wraps it automatically!
model_with_tools = llm.bind_tools([SendSlots])

def llm_node(state: AgentState):
    """Run LLM with full conversation history and bound tools."""
    messages = state["messages"]
    response = model_with_tools.invoke(messages)
    return {"messages": [response]} 

# 3. Build StateGraph
graph = StateGraph(AgentState)
graph.add_node("model", llm_node)
graph.set_entry_point("model")
graph.add_edge("model", END)

checkpointer = MemorySaver()
root_agent = graph.compile(checkpointer=checkpointer)

def build_message_payload(user_input: Union[str, dict]):
    """
    Creates the LangGraph input payload.
    Handles both simple text (str) and multimodal content (dict).
    """
    message_content = []

    if isinstance(user_input, str):
        message_content = user_input
    
    elif isinstance(user_input, dict) and user_input.get("role") == "user" and "content" in user_input:
        for part in user_input["content"]:
            if part.get("type") == "text" and part.get("text"):
                message_content.append({"type": "text", "text": part["text"]})
            
            elif part.get("type") == "image":
                mime_type = part.get("mime_type", "image/jpeg")
                base64_data = part["base64"]
                message_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{base64_data}"}
                })
            else:
                message_content.append(part)
    else:
        raise ValueError("User input must be a string or a multimodal dict.")

    return {
        "messages": [HumanMessage(content=message_content)]
    }