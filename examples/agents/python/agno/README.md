# 🎙️ Agno + Zijus Chat UI Integrations

This repository contains a production-ready **FastAPI** example demonstrating how to seamlessly integrate the **[Zijus Chat UI](https://github.com/zijus/zijus-chat-ui)** with the **[Agno Framework](https://github.com/agno-agi/agno)**.

This example goes beyond simple text chat, showcasing advanced conversational AI features like **multimodal file processing**, and **interactive UI widgets** using our framework-agnostic `zijus-tools` library.

---

## 🌟 Key Features Demonstrated
* **Rich UI Rendering:** Uses `zijus-tools` to let the Agno agent render buttons, forms, and dynamic slots natively in the chat client.
* **Multimodal Ready:** Safely parses images directly into `AgnoImage` and extracts documents (TXT/CSV placeholders included).
* **Secure JWT Sessions:** Manages WebSocket security and thread-safe connections.

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
* `OPENAI_API_KEY`: Your API key for the Agno Agent.
* `JWT_SECRET_KEY`: Used in `utils.py` to securely sign WebSocket sessions.
* `APP_NAME`: Name of your agent.

---

## 🧩 Agent Setup 

The core logic for your Agno agent lives inside:
```
my_agent/agent.py
```

This file contains the **agent definition**, model configuration, tools, and instructions. 

### ✅ Customize your Agent:
1. Open `my_agent/agent.py`.
2. Modify the agent’s logic as desired:
   - Configure system instructions.
   - Import and add tools from `zijus_tools` (e.g., `from zijus_tools import SendSlots`) to the `tools=[]` array to give your agent UI superpowers.
   - Attach databases (`AsyncSqliteDb`) for persistence.

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