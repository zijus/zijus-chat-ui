# 🎙️ Microsoft AutoGen + Zijus Chat UI Integrations

This repository contains a production-ready **FastAPI** example demonstrating how to flawlessly integrate the **[Zijus Chat UI](https://github.com/zijus/zijus-chat-ui)** with **[Microsoft AutoGen](https://github.com/microsoft/autogen)**.

AutoGen is famously used for building Multi-Agent Systems. This example solves one of AutoGen's biggest hurdles: **Human-in-the-loop Web UIs.** It demonstrates how AutoGen agents can trigger UI components natively inside a web chat instead of relying on a terminal!

---

## 🌟 Key Features Demonstrated
* **Human-in-the-Loop UI:** Demonstrates how to expose interactive Web UI tools (sliders, buttons) directly to AutoGen agents using our framework-agnostic `zijus-tools` package.
* **Session Memory Isolation:** Implements an `AgentManager` that spins up isolated `AssistantAgent` instances for each WebSocket connection, ensuring conversation state doesn't leak between browser tabs.
* **Native Vision Support:** Automatically translates uploaded files from the chat into AutoGen's native `AGImage` and `MultiModalMessage` formats.
* **Typewriter Streaming:** Parses AutoGen's `ModelClientStreamingChunkEvent` to render smooth, real-time typing in the UI.

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

AutoGen tools require strict typing. We use standard async python functions to wrap the Zijus tools and pass them directly into the AutoGen agent:

```python
from zijus_tools import SendSlider

async def send_slider_tool(content: str, min_value: int, max_value: int, default_value: int) -> str:
    """Renders an interactive range slider in the chat UI."""
    await SendSlider(content=content, min_value=min_value, max_value=max_value, default_value=default_value)
    
    # Return a message telling AutoGen to wait for the UI response!
    return "UI rendered successfully. Stop generating and wait for the user."
```

### 🧪 Advanced Idea: Multi-Agent Teams
You can easily expand this example into an AutoGen `GroupChat`! Simply update the `AgentManager` in `agent.py` to return a Team instead of a single `AssistantAgent`. As the agents talk to each other, the Zijus UI will render all of their messages dynamically to the human observer!

---

## 🚀 Running the Example

Start the FastAPI app:

```bash
uvicorn main:app --reload
```

Open **http://localhost:8000** in your browser to interact with the AutoGen backend!

---

## 🎨 Customizing the Zijus Chat UI

Visit our visual editor to style the client:
👉 **[https://www.zijus.com/zijus-chat-ui](https://www.zijus.com/zijus-chat-ui?utm_source=github)**

Use the generator to create a **custom embed configuration** that matches your preferred style, colors, typography, and avatar. Once generated, simply paste the encoded configuration string into your `.env` file under `ZIJUS_CONFIG_ENCODED`.