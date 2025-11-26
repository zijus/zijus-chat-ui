# Google ADK + Zijus Chat UI Examples

This directory contains **two example FastAPI applications** demonstrating how to integrate the **Zijus Chat UI** with a simple **Google ADK agent**.
You can choose between:

1. **normal-streaming** – standard text streaming
2. **bidi-streaming** – bidirectional streaming (UI → backend → UI)

Both examples run independently and include a working FastAPI server + sample ADK agent + Zijus Chat UI configuration.

---

## 🚀 Getting Started

### 1. Create & activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows
```

### 2. Install dependencies

Each folder has its own `requirements.txt`.
Install dependencies **inside the folder you want to run**:

```bash
cd normal-streaming          # or: cd bidi-streaming
pip install -r requirements.txt
```

---

## ⚙️ Environment Setup

Each example directory contains an `env-sample` file.

1. **Copy it:**

```bash
cp env-sample .env
```

2. **Edit `.env`** and update values as needed.

> The default configuration assumes your FastAPI server runs at
> **[http://localhost:8000](http://localhost:8000)**, so no changes are required for local use.

---

## 🧪 Running the Examples

Move into the example you want to run:

```bash
cd normal-streaming
# or
cd bidi-streaming
```

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

👉 **[https://www.zijus.com/zijus-chat-ui](https://www.zijus.com/zijus-chat-ui)**

Use the generator to create a **custom embed configuration** that matches your preferred style, colors, or layout.
Replace the generated config in the .env file as needed.

---

## 💬 Try Your Agent

Once the server is running, open your browser:

```
http://localhost:8000
```

You should now see the **Zijus Chat UI** and be able to interact with your ADK agent in either:

* **normal streaming mode**, or
* **bidirectional streaming mode**

depending on which example you launched.

