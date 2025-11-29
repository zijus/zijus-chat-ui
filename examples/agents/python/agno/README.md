# Agno + Zijus Chat UI Examples

This directory contains a **FastAPI application** demonstrating how to integrate the **Zijus Chat UI** with a simple **Agno Agent**.

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

👉 **[https://www.zijus.com/zijus-chat-ui](https://www.zijus.com/zijus-chat-ui?utm_source=github)**

Use the generator to create a **custom embed configuration** that matches your preferred style, colors, or layout.
Replace the generated config in the .env file as needed.

---

## 💬 Try Your Agent

Once the server is running, open your browser:

```
http://localhost:8000
```

You should now see the **Zijus Chat UI** and be able to interact with your Agno agent

---

## 💬 Placeholder Functions

The `utils.py` file has some placeholder helper functions that need to be updated as desired

