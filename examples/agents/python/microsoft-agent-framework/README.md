# 🎙️ Microsoft Agent Framework + Zijus Chat UI Integrations

This repository contains a production-ready **FastAPI** example demonstrating how to seamlessly integrate the **[Zijus Chat UI](https://github.com/zijus/zijus-chat-ui)** with the **[Microsoft Agent Framework (v1.2.0+)](https://github.com/microsoft/agent-framework)**.

This example goes beyond simple text chat, showcasing advanced conversational AI features like **multimodal file processing**, and **interactive UI widgets** using our framework-agnostic `zijus-tools` library.

---

## 🌟 Key Features Demonstrated
* **Unified Messaging API:** Demonstrates how to properly format and send multimodal text/image lists via Microsoft's v1.2.0 unified `Message` object.
* **Stream Iteration:** Showcases how to safely execute and parse the Microsoft `Agent.run(stream=True)` asynchronous generator.
* **State Machine Prompting:** Features "Finny", a Financial Assistant, utilizing a highly constrained prompt that completely eliminates LLM tool hallucination.
* **Interactive UI Rendering:** Shows exactly how to wrap asynchronous python functions (like `SendSlots`) to natively render Zijus UI widgets directly from the LLM.

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

## 🧩 Agent Setup 

The core logic for your agent lives inside:
```
my_agent/agent.py
```

### Connecting to OpenAI
Unlike older versions of the framework, v1.2.0 allows you to directly construct a native client, bypassing Azure endpoints entirely. We achieve this by importing `OpenAIChatClient`:

```python
from agent_framework.openai import OpenAIChatClient

client = OpenAIChatClient(
    api_key=OPENAI_API_KEY,
    model="gpt-5.4-mini"
)
```

### Wrapping UI Tools
You can expose any Python function to the agent via the `tools` array. When `zijus-tools` are fired, they render custom UI components directly on the frontend:

```python
from zijus_tools import SendSlider

async def send_slider_tool(content: str, min_value: int, max_value: int, default_value: int) -> str:
    """Renders an interactive range slider in the chat UI."""
    await SendSlider(content=content, min_value=min_value, max_value=max_value, default_value=default_value)
    return "UI rendered successfully. Stop generating and wait for the user."
```

---

## 🧪 Running the Example

Start the FastAPI app:

```bash
uvicorn main:app --reload
```

By default, the server starts on **http://localhost:8000**. Open this in your browser to interact with the Zijus Chat UI!

---

## 🎨 Customizing the Zijus Chat UI

Visit our visual editor to style the client:
👉 **[https://www.zijus.com/zijus-chat-ui](https://www.zijus.com/zijus-chat-ui?utm_source=github)**

Use the generator to create a **custom embed configuration** that matches your preferred style, colors, typography, and avatar. Once generated, simply paste the encoded configuration string into your `.env` file under `ZIJUS_CONFIG_ENCODED`.