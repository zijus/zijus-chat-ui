# 🎙️ Google ADK + Zijus Chat UI Integrations

This repository contains production-ready **FastAPI** examples demonstrating how to seamlessly integrate the **[Zijus Chat UI](https://github.com/zijus/zijus-chat-ui)** with the **[Google Agent Development Kit (ADK)](https://adk.dev/get-started/python/)**.

These examples go beyond simple text chat, showcasing advanced conversational AI features like **real-time voice barge-in**, **multimodal file processing**, and **interactive UI widgets** using our framework-agnostic `zijus-tools` library.

The examples are organized into two folders:
* ⚡ `bidi-streaming` - Uses Google's Live API (`StreamingMode.BIDI`) for ultra-low latency, real-time native audio conversations (e.g., `gemini-2.5-flash-native-audio-preview-12-2025`). 
* 💬 `normal-streaming` - Uses Standard Server-Sent Events (`StreamingMode.SSE`) for text and traditional text-to-speech workflows. Includes background task processing to allow seamless user interruptions.

---

## 🌟 Key Features Demonstrated
* **Rich UI Rendering:** Uses `zijus-tools` to let the agent render buttons, forms, and dynamic slots natively in the chat client.
* **Multimodal Ready:** Safely handles image and document uploads (TXT/CSV placeholders included).
* **Secure JWT Sessions:** Shows how to manage WebSocket security and thread-safe connections.

---

## 🚀 Getting Started

### 1. Create & activate a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows
```

### 2. Install dependencies
Navigate to the folder you want to run (`bidi-streaming` or `normal-streaming`) and install the requirements. 
*(Note: These examples utilize `zijus-tools` to render UI components).*
```bash
pip install -r requirements.txt
```

---

## ⚙️ Environment Setup

There is a `env-sample` file in each folder.

1. **Copy it to create your local environment file:**
```bash
cp env-sample .env
```

2. **Edit `.env`** and update the required values:
* `GEMINI_API_KEY`: Your Google Gemini API key (Required for the ADK).
* `JWT_SECRET_KEY`: Used in `utils.py` to securely sign WebSocket sessions.
* `APP_NAME`: Name of your agent.

> The default configuration assumes your FastAPI server runs at **http://localhost:8000**, so no changes are required for local development.

---

## 🧩 Agent Setup (Required Before Running)

The core logic for your Google ADK agent lives inside:
```
my_agent/agent.py
```

This file contains the **agent definition**, including model configuration, tools, and instructions. 

### ✅ Before starting the server:
1. Open `my_agent/agent.py`.
2. Modify the agent’s logic as desired:
   - Configure system instructions.
   - Import and add tools from `zijus_tools` (e.g., `from zijus_tools import SendSlots`) to give your agent UI superpowers.
   - Customize workflows or add your own Python functions.

📘 **Need help with Google ADK capabilities?**
See the official documentation: **[https://google.github.io/adk-docs/](https://google.github.io/adk-docs/)**

---

## 🧪 Running the Examples

Navigate to the specific folder (`bidi-streaming` or `normal-streaming`) and start the FastAPI app:

```bash
uvicorn main:app --reload
```

By default, the server starts on:
**http://localhost:8000**

---

## 🎨 Customizing the Zijus Chat UI

Visit our visual editor to style the client:
👉 **[https://www.zijus.com/zijus-chat-ui](https://www.zijus.com/zijus-chat-ui?utm_source=github)**

Use the generator to create a **custom embed configuration** that matches your preferred style, colors, typography, and avatar. Once generated, simply paste the encoded configuration string into your `.env` file under `ZIJUS_CONFIG_ENCODED`.

---

## 🔧 Architecture & Placeholders

* `main.py`: Contains the FastAPI WebSocket loop, Google ADK execution engine, and barge-in state management.
* `utils.py`: Contains placeholder helper functions. By default, it includes a basic text extractor for `.txt` and `.csv` uploads, and JWT generation logic. Connect these to your production database, document parsers (like GCP Document AI), or email providers.