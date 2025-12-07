# 🤝 Contributing to Zijus Chat UI

Thank you for your interest in contributing to **Zijus Chat UI**!
We welcome contributions of all kinds — bug fixes, new examples, documentation improvements, and feature suggestions.

This project powers the **Zijus platform** and is actively maintained. Your contributions help improve the ecosystem for everyone building agentic applications.

---

# 🧭 How You Can Contribute

### ✅ **1. Report Bugs**

If you encounter a bug or unexpected behavior:

* Open an issue on GitHub
* Include reproduction steps, logs, or screenshots when possible
* Mention your environment (OS, Python version, framework used, etc.)

👉 **Issues:** [https://github.com/zijus/zijus-chat-ui/issues](https://github.com/zijus/zijus-chat-ui/issues)

---

### ✅ **2. Suggest Features or Improvements**

We’re always looking to improve:

* Framework support
* UI customization options
* Backend integration patterns
* Docs & tutorials

Please check if an issue already exists — if not, open one with the **Feature Request** template.

---

### ✅ **3. Add or Improve Examples**

You can add examples for frameworks such as:

* LangChain
* Agno
* Autogen
* Google ADK
* Microsoft Agent Framework
* AWS Strands
* Custom agentic stacks

Each example includes:

```
my_agent/agent.py
utils.py
main.py
requirements.txt
env-sample
templates/index.html
README.md
```

Follow the structure of existing examples for consistency.

---

### ✅ **4. Improve Documentation**

Helpful documentation includes:

* README updates
* Step-by-step setup guides
* Inline comments
* Troubleshooting notes

Good docs dramatically improve onboarding for new developers.

---

### ✅ **5. Contribute to Backend Adapters**

The WebSocket backend and message translation helpers (`utils.py`) are open-source.
You can improve:

* Response formatting
* Stream handling
* Error management
* Framework adapters

---

# 🛠 Development Setup

### Clone repo:

```bash
git clone https://github.com/zijus/zijus-chat-ui
cd zijus-chat-ui
```

### Install dependencies for an example (e.g., Agno):

```bash
cd examples/agents/python/agno
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run the backend:

```bash
uvicorn main:app --reload
```

The UI demo is located in:

```
templates/index.html
```

Modify and test as needed.

---

# 🔄 Submitting Pull Requests

### Before submitting:

* Ensure your PR is scoped and focused
* Add comments where clarity is needed
* Update or include example/README changes when relevant
* Run the example to ensure it works end-to-end

### PR requirements:

* Clear title and description
* Explanation of context and purpose
* Screenshots or logs (if UI-related)
* Reference any related issue IDs

We will review PRs as quickly as possible.

---

# 🧹 Code Style Guidelines

### Python

* Follow PEP 8 standards
* Use clear, descriptive function names
* Document anything non-obvious

### JavaScript (UI embed usage only)

* Keep usage examples simple and copy-paste friendly

### Examples

* Maintain the existing folder structure
* Mirror the consistency of current framework examples

---

# 🔐 Licensing

By contributing, you agree that:

* Your contributions are submitted under the repository's license
* You are the original author of the contributed code

---

# 🌟 Thank You!

Your contributions help improve the developer experience for thousands of engineers building LLM agents across frameworks.

If you like the project, please consider:

* ⭐ Starring the repo
* Sharing it with your community
* Submitting issues or PRs
* Helping others in GitHub Discussions

We’re excited to build this ecosystem with you!
