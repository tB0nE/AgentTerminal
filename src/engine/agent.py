import json
import threading
import queue
from fastapi import FastAPI, Request
import uvicorn
from src.engine.llm import APIHandler
from tools.file_io import read_file, write_file, list_dir
from tools.research import web_search, fetch_url
from rich.console import Console
from rich.panel import Panel

console = Console()

# Global queue for messages arriving via the FastAPI server
external_message_queue = queue.Queue()

app = FastAPI()

@app.post("/message")
async def receive_message(request: Request):
    """External API endpoint to inject tasks into the agent system."""
    data = await request.json()
    sender = data.get("sender", "Unknown")
    message = data.get("message", "")
    
    external_message_queue.put({"sender": sender, "message": message})
    return {"status": "Message received by WriterAgent"}

def start_server():
    """Starts the FastAPI server on the designated port."""
    from config.settings import SERVER_PORT
    uvicorn.run(app, host="127.0.0.1", port=SERVER_PORT, log_level="error")

# The core prompt template that defines the agent's behavior and JSON-only response format
BASE_SYSTEM_PROMPT = """You are {name}, a specialized AI agent.
Your Role: {role}

Your goal is to fulfill tasks by reasoning (Thought) and taking action (Tool Call).
If you receive a task from another agent or user, complete it and notify them back if needed.

STRICT OUTPUT FORMAT:
You must ALWAYS respond with a JSON object. No other text.
Format 1 (Reasoning/Acting):
{{
  "thought": "Internal monologue about what to do next.",
  "tool_call": {{"name": "tool_name", "args": {{"arg_name": "value"}}}}
}}

Format 2 (Updating Scratchpad):
{{
  "thought": "I need to update my current progress.",
  "tool_call": {{"name": "update_scratchpad", "args": {{"text": "Updated goal state..."}}}}
}}

Format 3 (Completion / Messaging):
{{
  "thought": "I have completed the task.",
  "final_answer": "Summary of what was done."
}}

AVAILABLE TOOLS:
{tools_list}
- delegate_task(agent_name, message): Sends a task to another agent.
- update_scratchpad(text): Updates your persistent memory.

Always use 'thought' to explain your plan before using a tool."""

class ContextManager:
    """Manages the conversation history and sliding window for an agent."""
    def __init__(self, system_prompt: str, max_turns: int = 10):
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.history = []
        self.scratchpad = "No current goal set."

    def get_full_prompt(self, user_goal: str = None) -> list:
        """Constructs the full list of messages for the LLM API call."""
        dynamic_system = f"{self.system_prompt}\n\nCURRENT SCRATCHPAD:\n{self.scratchpad}"
        messages = [{"role": "system", "content": dynamic_system}]
        
        # Sliding window: keep only the most recent N turns (user + assistant)
        recent_history = self.history[-(self.max_turns * 2):] if self.history else []
        messages.extend(recent_history)
        
        if user_goal:
            msg = {"role": "user", "content": user_goal}
            messages.append(msg)
            self.history.append(msg)
            
        return messages

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})

    def update_scratchpad(self, text: str) -> str:
        self.scratchpad = text
        return "Scratchpad updated."

class Agent:
    """
    An autonomous worker that follows the ReAct pattern.
    Processes tasks from a queue and executes tools until a final answer is reached.
    """
    def __init__(self, config_path: str, orchestrator):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
            
        self.name = self.config.get("name", "Unknown")
        self.role = self.config.get("role", "")
        self.allowed_tools = self.config.get("tools", [])
        self.orchestrator = orchestrator
        
        # Format tools list for the system prompt
        tools_list_str = "\\n".join([f"- {t}" for t in self.allowed_tools if t not in ["delegate_task", "update_scratchpad"]])
        sys_prompt = BASE_SYSTEM_PROMPT.format(name=self.name, role=self.role, tools_list=tools_list_str)
        
        self.api = APIHandler()
        self.memory = ContextManager(sys_prompt)
        self.msg_queue = queue.Queue()
        self.is_working = False
        self.ui_logs = [] # Stores history for the UI dashboard

    def log_ui(self, msg_type: str, content: str):
        """Helper to store structured logs for display in the UI panels."""
        self.ui_logs.append({"type": msg_type, "content": content})
        
    def get_logs(self):
        return self.ui_logs

    def process_queue(self):
        """
        Pulls one task from the queue and runs the autonomous ReAct loop.
        Returns True if a task was processed, False otherwise.
        """
        if self.msg_queue.empty():
            return False
            
        self.is_working = True
        task = self.msg_queue.get()
        sender = task.get("sender", "System")
        message = task.get("message", "")
        
        self.log_ui("user", f"[{sender}] {message}")
        user_goal = f"Message from {sender}: {message}"
        messages = self.memory.get_full_prompt(user_goal)
        
        # --- THE REACT LOOP ---
        while True:
            response = self.api.call_llm(messages)
            
            if "error" in response:
                self.log_ui("error", response['error'])
                break
                
            thought = response.get("thought", "Thinking...")
            self.log_ui("thought", thought)
            
            # Action Phase
            if "tool_call" in response:
                tool_data = response["tool_call"]
                t_name = tool_data["name"]
                t_args = tool_data.get("args", {})
                
                self.log_ui("tool", f"{t_name}({t_args})")
                
                # Tool Dispatcher
                if t_name == "update_scratchpad":
                    result = self.memory.update_scratchpad(t_args.get("text", ""))
                elif t_name == "delegate_task":
                    target = t_args.get("agent_name")
                    msg = t_args.get("message")
                    self.orchestrator.send_message(self.name, target, msg)
                    result = f"Task delegated to {target}."
                elif t_name == "read_file" and "read_file" in self.allowed_tools: result = read_file(**t_args)
                elif t_name == "write_file" and "write_file" in self.allowed_tools: result = write_file(**t_args)
                elif t_name == "list_dir" and "list_dir" in self.allowed_tools: result = list_dir(**t_args)
                elif t_name == "web_search" and "web_search" in self.allowed_tools: result = web_search(**t_args)
                elif t_name == "fetch_url" and "fetch_url" in self.allowed_tools: result = fetch_url(**t_args)
                else:
                    result = f"Error: Tool {t_name} not found or not permitted for this agent."
                
                self.log_ui("result", str(result))
                
                # Update memory with the interaction
                self.memory.add_message("assistant", json.dumps(response))
                self.memory.add_message("user", f"Tool Output: {result}")
                messages = self.memory.get_full_prompt()
                
            # Completion Phase
            elif "final_answer" in response:
                ans = response["final_answer"]
                self.log_ui("final", ans)
                break
            else:
                self.log_ui("error", "Unexpected LLM output format.")
                break
                
        self.is_working = False
        self.msg_queue.task_done()
        return True
