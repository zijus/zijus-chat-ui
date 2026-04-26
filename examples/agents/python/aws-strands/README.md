# 🎙️ AWS Strands + Zijus Chat UI Integrations

This repository contains a production-ready **FastAPI** example demonstrating how to seamlessly integrate the **[Zijus Chat UI](https://github.com/zijus/zijus-chat-ui)** with the **[AWS Strands Framework](https://github.com/awslabs/strands-agents)**.

This example goes beyond simple text chat. It showcases advanced conversational AI features like **multimodal file routing**, and **interactive UI widgets** via our framework-agnostic `zijus-tools` library.

---

## 🌟 Key Features Demonstrated
* **Interactive UI Rendering:** Shows exactly how to wrap `zijus-tools` using the Strands `@tool` decorator to render buttons, sliders, and forms natively in the chat client.
* **State Machine Prompting:** Features "Finny", a Financial Assistant, utilizing a highly constrained prompt that completely eliminates LLM tool hallucination.
* **OpenAI v1.0+ Compatibility:** Demonstrates how to bypass proxy initialization bugs by safely injecting a persistent `httpx.AsyncClient` directly into the Strands `OpenAIModel`.
* **File-based Memory:** Uses the native Strands `FileSessionManager` to maintain perfect conversation history across UI interactions and WebSocket reconnects.

---

## 🚀 Getting Started

### 1. Create & activate a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows
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
* `OPENAI_API_KEY`: Your API key for the GPT model.
* `JWT_SECRET_KEY`: Used in `utils.py` to securely sign WebSocket sessions.
* `APP_NAME`: Name of your agent.

> The default configuration assumes your FastAPI server runs at **http://localhost:8000**.

---

## 🧩 Agent Architecture (`my_agent/agent.py`)

The core logic for your AWS Strands agent lives inside `my_agent/agent.py`.

### Wrapping UI Tools
Because AWS Strands requires tools to be strictly typed and explicitly decorated, we demonstrate how to wrap the asynchronous `zijus-tools` functions:

```python
from strands.tools import tool
from zijus_tools import SendSlider

@tool
async def send_slider_tool(content: str, min_value: int, max_value: int, default_value: int) -> str:
    """Renders an interactive range slider in the chat UI."""
    await SendSlider(content=content, min_value=min_value, max_value=max_value, default_value=default_value)
    return "UI rendered successfully. Stop generating and wait for the user."
```

### ✅ Customizing your Agent:
1. Open `my_agent/agent.py`.
2. Modify the `instructions` variable to change the agent's persona.
3. Add more tools from `zijus_tools` and pass them into the `tools=[]` array when initializing the `Agent`.
4. The `FileSessionManager` automatically stores conversation histories in the `./tmp/strands_sessions` folder.

---

## 🧪 Running the Example

Start the FastAPI app:

```bash
uvicorn main:app --reload
```

Open your browser to **http://localhost:8000** to interact with Finny the Financial Assistant! 
You will see Finny immediately open a UI slider to ask for a loan amount instead of relying on pure text extraction.

---

## 🎨 Customizing the Zijus Chat UI

Visit our visual editor to style the client:
👉 **[https://www.zijus.com/zijus-chat-ui](https://www.zijus.com/zijus-chat-ui?utm_source=github)**

Use the generator to create a **custom embed configuration** that matches your preferred style, colors, typography, and avatar. Once generated, simply paste the encoded configuration string into your `.env` file under `ZIJUS_CONFIG_ENCODED`.