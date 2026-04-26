# 🎙️ LangChain / LangGraph + Zijus Chat UI Integrations

This repository contains a production-ready **FastAPI** example demonstrating how to flawlessly integrate the **[Zijus Chat UI](https://github.com/zijus/zijus-chat-ui)** with **[LangChain & LangGraph](https://github.com/langchain-ai/langgraph)**.

LangGraph is the industry standard for building cyclical, stateful AI agents. This example demonstrates how to give your LangGraph state machines a powerful, interactive frontend by native rendering UI components directly from the execution graph!

---

## 🌟 Key Features Demonstrated
* **Tool-Driven UIs:** Demonstrates how to wrap our framework-agnostic `zijus-tools` using LangChain's `@tool` decorator. The LangGraph `ToolNode` automatically executes these functions to render Sliders and Buttons in the chat UI!
* **Native StateGraphs:** Bypasses deprecated agent wrappers in favor of a pure, robust `StateGraph` implementation with conditional tool routing.
* **Stream Filtering:** Shows exactly how to parse the LangGraph `astream(stream_mode="messages")` output to filter out internal `ToolMessage` execution logs so only clean AI text is streamed to the frontend.
* **Stateful Sessions:** Implements `MemorySaver` checkpointers to ensure the graph remembers conversation history across WebSocket disconnects and reconnects.
* **Native Multimodal Support:** Automatically formats image attachments into LangChain's standard `HumanMessage` dictionary schema for seamless vision analysis.

---

## 🚀 Getting Started

### 1. Create & activate a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate         # Windows
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

---

## ⚙️ Environment Setup

1. **Create your local environment file:**
```bash
cp env-sample .env
```

2. **Edit `.env`** and update the required values:
* `OPENAI_API_KEY`: Your API key for the `gpt-4o-mini` model.
* `JWT_SECRET_KEY`: Used in `utils.py` to securely sign WebSocket sessions.
* `APP_NAME`: Name of your agent.

---

## 🧩 Agent Setup (`my_agent/agent.py`)

LangChain makes adding UI tools incredibly simple. Just decorate your asynchronous Zijus components with `@tool` and pass them into your `StateGraph` via a `ToolNode`:

```python
from langchain_core.tools import tool
from zijus_tools import SendSlider

@tool
async def send_slider_tool(content: str, min_value: int, max_value: int, default_value: int) -> str:
    """Renders an interactive range slider in the chat UI."""
    await SendSlider(content=content, min_value=min_value, max_value=max_value, default_value=default_value)
    
    # Let the LangGraph execution flow know the tool succeeded!
    return "UI rendered successfully. Stop generating and wait for the user."
```

When building the graph, you simply compile the Tool Node alongside your LLM:
```python
tool_node = ToolNode(tools=[send_slider_tool])
graph_builder.add_node("tools", tool_node)
```

---

## 🚀 Running the Example

Start the FastAPI app:

```bash
uvicorn main:app --reload
```

Open **http://localhost:8000** in your browser to test the reactive LangGraph agent!

---

## 🎨 Customizing the Zijus Chat UI

Visit our visual editor to style the client:
👉 **[https://www.zijus.com/zijus-chat-ui](https://www.zijus.com/zijus-chat-ui?utm_source=github)**

Use the generator to create a **custom embed configuration** that matches your preferred style, colors, typography, and avatar. Once generated, simply paste the encoded configuration string into your `.env` file under `ZIJUS_CONFIG_ENCODED`.