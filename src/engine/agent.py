import json
import threading
import queue
import os
import traceback
from fastapi import FastAPI, Request
import uvicorn
from src.engine.llm import APIHandler
from tools.file_io import read_file, write_file, list_dir
from tools.research import web_search, fetch_url
from src.utils.logger import log_debug, log_info, log_error
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

# The core prompt template
BASE_SYSTEM_PROMPT = """You are {name}, a specialized AI agent.
Your Role: {role}

Your goal is to fulfill tasks by reasoning (Thought) and taking action (Tool Call).
If you receive a task from another agent or user, complete it and notify them back if needed.

RESTRICTION: You cannot write to or modify files in the 'project/reference/' directory. These are read-only source materials.

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

TOOL_DESCRIPTIONS = {
    "read_file": "read_file(path): Returns content of a file.",
    "write_file": "write_file(path, content): Writes/overwrites a file.",
    "list_dir": "list_dir(directory): Lists items in a directory.",
    "web_search": "web_search(query): Searches the web.",
    "fetch_url": "fetch_url(url): Reads text from a URL."
}

class ContextManager:
    """Manages the conversation history and sliding window for an agent."""
    def __init__(self, system_prompt: str, max_turns: int = 15):
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.history = []
        self.scratchpad = "No current goal set."

    def get_full_prompt(self, user_goal: str = None) -> list:
        """Constructs the full list of messages for the LLM API call."""
        dynamic_system = f"{self.system_prompt}\n\nCURRENT SCRATCHPAD:\n{self.scratchpad}"
        messages = [{"role": "system", "content": dynamic_system}]
        
        recent_history = self.history[-(self.max_turns * 2):] if self.history else []
        messages.extend(recent_history)
        
        if user_goal:
            msg = {"role": "user", "content": user_goal}
            messages.append(msg)
            
        return messages

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})

    def update_scratchpad(self, text: str) -> str:
        self.scratchpad = text
        return "Scratchpad updated."

class Agent:
    def __init__(self, config_path: str, orchestrator):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
            
        self.name = self.config.get("name", "Unknown")
        self.role = self.config.get("role", "")
        self.allowed_tools = self.config.get("tools", [])
        self.orchestrator = orchestrator
        
        tools_list_items = []
        for t in self.allowed_tools:
            if t in TOOL_DESCRIPTIONS:
                tools_list_items.append(f"- {TOOL_DESCRIPTIONS[t]}")
            elif t not in ["delegate_task", "update_scratchpad"]:
                tools_list_items.append(f"- {t}")
        
        tools_list_str = "\\n".join(tools_list_items)
        sys_prompt = BASE_SYSTEM_PROMPT.format(name=self.name, role=self.role, tools_list=tools_list_str)
        
        self.api = APIHandler()
        self.memory = ContextManager(sys_prompt)
        self.msg_queue = queue.Queue()
        self.is_working = False
        
        # New: Interrupt and Interjection support
        self.interrupt_flag = False
        self.interjection_queue = queue.Queue()
        
        self.log_path = f"logs/{self.name}_ui.json"
        self.history_path = f"logs/{self.name}_history.json"
        self.ui_logs = [] 
        self.load_persistence()

    def load_persistence(self):
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, 'r') as f: self.ui_logs = json.load(f)
            except: pass
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, 'r') as f: self.memory.history = json.load(f)
            except: pass

    def save_persistence(self):
        os.makedirs("logs", exist_ok=True)
        try:
            with open(self.log_path, 'w') as f: json.dump(self.ui_logs, f, indent=2)
            with open(self.history_path, 'w') as f: json.dump(self.memory.history, f, indent=2)
        except: pass

    def log_ui(self, msg_type: str, content: str):
        self.ui_logs.append({"type": msg_type, "content": content})
        self.save_persistence()
        
    def get_logs(self):
        return self.ui_logs

    def process_queue(self):
        """Processes tasks with support for interrupts and mid-loop corrections."""
        if self.msg_queue.empty():
            return False
            
        self.is_working = True
        self.interrupt_flag = False
        task = self.msg_queue.get()
        sender, message = task.get("sender", "System"), task.get("message", "")
        
        self.log_ui("user", f"[{sender}] {message}")
        self.memory.add_message("user", f"Message from {sender}: {message}")
        self.save_persistence()
        
        while True:
            # Check for hard interrupt
            if self.interrupt_flag:
                self.log_ui("error", "Task interrupted by user.")
                break

            # Check for interjections (mid-loop messages)
            try:
                while True:
                    inter = self.interjection_queue.get_nowait()
                    inter_msg = f"INTERJECTION from {inter['sender']}: {inter['message']}"
                    self.log_ui("user", inter_msg)
                    self.memory.add_message("user", inter_msg)
                    self.save_persistence()
            except queue.Empty:
                pass

            messages = self.memory.get_full_prompt()
            response = self.api.call_llm(messages)
            
            if "error" in response:
                self.log_ui("error", response['error'])
                break
                
            thought = response.get("thought", "Thinking...")
            self.log_ui("thought", thought)
            
            if "tool_call" in response:
                tool_data = response["tool_call"]
                t_name, t_args = tool_data["name"], tool_data.get("args", {})
                self.log_ui("tool", f"{t_name}({t_args})")
                
                try:
                    if t_name == "update_scratchpad":
                        result = self.memory.update_scratchpad(t_args.get("text", ""))
                    elif t_name == "delegate_task":
                        target, msg = t_args.get("agent_name"), t_args.get("message")
                        if self.orchestrator.send_message(self.name, target, msg):
                            result = f"Task delegated to {target}."
                        else:
                            result = f"Error: Target agent '{target}' not found."
                    elif t_name == "read_file" and "read_file" in self.allowed_tools: result = read_file(**t_args)
                    elif t_name == "write_file" and "write_file" in self.allowed_tools: result = write_file(**t_args)
                    elif t_name == "list_dir" and "list_dir" in self.allowed_tools: result = list_dir(**t_args)
                    elif t_name == "web_search" and "web_search" in self.allowed_tools: result = web_search(**t_args)
                    elif t_name == "fetch_url" and "fetch_url" in self.allowed_tools: result = fetch_url(**t_args)
                    else:
                        result = f"Error: Tool {t_name} not found or not permitted for this agent."
                except Exception as e:
                    result = f"Error executing tool {t_name}: {str(e)}"
                
                self.log_ui("result", str(result))
                self.memory.add_message("assistant", json.dumps(response))
                self.memory.add_message("user", f"Tool Output: {result}")
                self.save_persistence()
                
            elif "final_answer" in response:
                ans = response["final_answer"]
                self.log_ui("final", ans)
                self.memory.add_message("assistant", json.dumps(response))
                self.save_persistence()
                break
            else:
                self.log_ui("error", "Unexpected LLM output format.")
                break
                
        self.is_working = False
        self.msg_queue.task_done()
        return True
