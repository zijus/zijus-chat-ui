# 🎙️ Google Agent Development Kit (ADK) + Zijus Chat UI Integrations

This repository contains production-ready **FastAPI** examples demonstrating how to deeply integrate the **[Zijus Chat UI](https://github.com/zijus/zijus-chat-ui)** with the new **[Google Agent Development Kit (ADK)](https://github.com/google/agent-development-kit)**.

Google ADK provides access to Gemini's incredibly fast, native **Live API**. These examples show you how to harness that power in a modern Web UI, complete with interactive widgets!

---

## 🌟 Two Modes of Operation

This repository includes two different `main.py` files demonstrating the two core ways to use Google ADK.

### 1. Normal Streaming (`normal-streaming/main.py`)
This is the traditional LLM approach. The user speaks or types, the audio is transcribed, and the text is sent to the LLM. The LLM streams text back.
* **Best for:** Chatbots, text-heavy workflows, and form filling.
* **Features:** Multimodal file uploads, async `Runner.run()` stream parsing, and native Zijus Tool execution.

### 2. Bidi / Realtime API (`bidi-streaming/main.py`)
This is the cutting-edge **Gemini Live API**. The user streams raw audio from their browser microphone directly into the LLM, and the LLM streams raw audio *back* natively. **No separate STT/TTS services required!**
* **Best for:** Voice agents, language practice, and ultra-low latency conversations.
* **Features:** 
    * **True Voice Barge-in:** If the user speaks while the bot is talking, the bot instantly aborts its audio playback.
    * **3-Tier State Machine:** Manages `NORMAL`, `PAUSED`, and `MUTED` audio states to prevent audio overlap.
    * **Realtime Metrics:** Logs precise millisecond latencies for STT, first text token, and first audio byte.

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
* `GEMINI_API_KEY`: Your Google Gemini API key.
* `JWT_SECRET_KEY`: Used in `utils.py` to securely sign WebSocket sessions.
* `APP_NAME`: Name of your agent.

---

## 🧩 Building the Agent (`my_agent/agent.py`)

Google ADK allows you to bind python functions seamlessly. We use the framework-agnostic `zijus-tools` package to render UI widgets directly from the LLM execution!

```python
from google.adk.agents import Agent
from zijus_tools import SendSlider

async def send_slider_tool(content: str, min_value: int, max_value: int, default_value: int) -> str:
    """Renders an interactive range slider in the chat UI."""
    await SendSlider(content=content, min_value=min_value, max_value=max_value, default_value=default_value)
    
    # Return a message telling ADK to pause generation and wait for the user to submit the form!
    return "UI rendered successfully. Stop generating and wait for the user."

# Pass tools directly into the ADK Agent
root_agent = Agent(
    model_name="models/gemini-2.0-flash-exp",
    tools=[send_slider_tool],
    instructions=instructions
)
```

---

## 🚀 Running the Examples

### Run the Bidi / Realtime Agent (Voice First)
```bash
uvicorn main_bidi:app --reload
```

### Run the Standard Agent (Text First)
*(Ensure you rename the file or point uvicorn to your standard implementation)*
```bash
uvicorn main_standard:app --reload
```

Open **http://localhost:8000** in your browser to interact with the agent!

---

## 🎨 Customizing the Zijus Chat UI

Visit our visual editor to style the web client:
👉 **[https://www.zijus.com/zijus-chat-ui](https://www.zijus.com/zijus-chat-ui?utm_source=github)**

Use the generator to create a **custom embed configuration** that matches your preferred style, colors, typography, and avatar. Once generated, simply paste the encoded configuration string into your `.env` file under `ZIJUS_CONFIG_ENCODED`.