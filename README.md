# Agent Terminal: A very slim terminal based agent manager to build any sort of project.

Built using Python, `rich`, and Z.ai's GLM-4 model via a custom ReAct orchestration loop.

## 🚀 Quick Start

1.  **Clone & Setup:**
    ```bash
    cd writer-agent
    python3 -m venv venv
    source venv/bin/activate
    pip install requests python-dotenv rich
    ```

2.  **Configure `.env`:**
    Create a `.env` file with your Z.ai credentials:
    ```env
    API_KEY=your_z_ai_api_key
    BASE_URL=https://open.bigmodel.cn/api/paas/v4/chat/completions
    MODEL_NAME=glm-4-flash
    ```

3.  **Run the Agent:**
    ```bash
    python main.py "Draft a dialogue script for Scene 1."
    ```

## 🧠 Core Architecture

-   **ReAct Orchestration:** The agent reasons ("Thought") and then acts ("Tool Call"). It continues this loop until it reaches a "Final Answer".
-   **Sliding Window Memory:** Prevents token-limit crashes by retaining only the most relevant messages.
-   **Local Toolset:** Directly manipulates local `.gd`, `.json`, and `.txt` files.
-   **Dynamic Scratchpad:** Persistent goal tracking in the system prompt.
