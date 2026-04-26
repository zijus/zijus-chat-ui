from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool
from typing import Annotated, TypedDict, Union
from dotenv import load_dotenv

# Import framework-agnostic UI tools
from zijus_tools import SendSlots, SendSlider

load_dotenv()

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

# --- WRAP ZIJUS TOOLS for LANGCHAIN ---
@tool
async def send_slots_tool(slots: list[str]) -> str:
    """Renders clickable choice buttons (slots) in the chat UI."""
    await SendSlots(slots=slots)
    return "UI rendered successfully. Stop generating and wait for the user."

@tool
async def send_slider_tool(content: str, min_value: int, max_value: int, default_value: int) -> str:
    """Renders an interactive range slider in the chat UI."""
    await SendSlider(content=content, min_value=min_value, max_value=max_value, default_value=default_value)
    return "UI rendered successfully. Stop generating and wait for the user."
# --------------------------------------

# 1. Define the State dictionary for the graph
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# 2. Initialize Model and Bind Tools
llm = ChatOpenAI(
    model="gpt-5.4-mini", 
    temperature=0.1,
    streaming=True
)
tools = [send_slots_tool, send_slider_tool]
llm_with_tools = llm.bind_tools(tools)

# 3. Create the LLM Node execution function
def chatbot(state: AgentState):
    # Ensure system prompt is always injected at the start of the evaluation
    messages = [SystemMessage(content=instructions)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

# 4. Build the Native State Graph
graph_builder = StateGraph(AgentState)

# Add Nodes
graph_builder.add_node("chatbot", chatbot)
tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)

# Add Edges
graph_builder.set_entry_point("chatbot")
# tools_condition automatically routes to "tools" if a tool was called, or END if finished.
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")

# Compile with memory
checkpointer = MemorySaver()
root_agent = graph_builder.compile(checkpointer=checkpointer)

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