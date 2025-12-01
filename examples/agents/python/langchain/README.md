# LangChain + Zijus Chat UI Examples

This directory contains a **FastAPI application** demonstrating how to integrate the **Zijus Chat UI** with a simple **LangChain Agent**.

---

## 🚀 Getting Started

### 1. Create & activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows
```

### 2. Install dependencies

Install dependencies from `requirements.txt`

---

## ⚙️ Environment Setup

There is a sample `env-sample` file.

1. **Copy it:**

```bash
cp env-sample .env
```

2. **Edit `.env`** and update values as needed.

> The default configuration assumes your FastAPI server runs at
> **[http://localhost:8000](http://localhost:8000)**, so no changes are required for local use.

---

## 🧩 Agent Setup (Required Before Running)

The core logic for your LangChain agent lives inside:

```
my_agent/agent.py
```

This file contains the **agent definition**, including chains, tools, model configuration, response logic, and behavior.

### ✅ Before starting the FastAPI server:

1. Open the file:

```
my_agent/agent.py
```

2. Modify the agent’s logic as desired:
   – Add tools
   – Configure or replace chains
   – Change prompts
   – Integrate external APIs
   – Customize response behavior

3. Save your changes.
   The FastAPI server will load this agent when it starts.

> If running with `--reload`, your changes to `agent.py` will auto-apply.

📘 **Need help with LangChain features, chains, or agent documentation?**
See the official docs: **[https://docs.langchain.com/oss/python/langchain/overview](https://docs.langchain.com/oss/python/langchain/overview)**

---

## 🧪 Running the Examples

Start the FastAPI app:

```bash
uvicorn main:app --reload
```

By default, the server starts on:

```
http://localhost:8000
```

This matches the default UI configuration.

---

## 🎨 Customizing the Zijus Chat UI

Visit:

👉 **[https://www.zijus.com/zijus-chat-ui?utm_source=github](https://www.zijus.com/zijus-chat-ui?utm_source=github)**

Use the generator to create a **custom embed configuration** that matches your preferred style, colors, or layout.
Replace the generated config in the `.env` file as needed.

---

## 💬 Try Your Agent

Once the server is running, open your browser:

```
http://localhost:8000
```

You should now see the **Zijus Chat UI** and be able to interact with your LangChain agent.

---

## 🔧 Placeholder Functions

The `utils.py` file contains placeholder helper functions that you may update or replace based on your needs.
