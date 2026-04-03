import json
import threading
import queue
import os
import traceback
from fastapi import FastAPI, Request
import uvicorn
from src.engine.llm import APIHandler
from tools.file_io import read_file, write_file, list_dir, copy_file, update_engine_registry
from tools.research import web_search, fetch_url
from tools.system import send_notification
from tools.comfy_api import generate_art
from tools.narrat import sync_narrat_config, validate_narrat_scripts
from tools.memory import store_memory, search_memory, ask_memory
from tools.character_manager import get_character_info, big_brain_query, search_character_images
from tools.messaging import send_user_response
from tools.tts import generate_voice
from tools.lifesim_tools import read_lifesim, create_lifesim, change_lifesim
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

MEMORY:
You have access to a Long-Term Memory API. Use `store_memory` when you learn something new about the user or world. Use `search_memory` to get broad context, and `ask_memory` for specific questions about things you might have forgotten. Always use your designated `namespace` (automatically managed) to keep your memories organized. For instance, the Writer and Lore Master share a namespace to ensure script and world consistency.

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
    "fetch_url": "fetch_url(url): Reads text from a URL.",
    "send_notification": "send_notification(message): Sends a desktop notification to the user.",
    "generate_art": "generate_art(prompt, workflow_name='Donut_Standard.json', character='Anya'): Generates an image using ComfyUI and saves it to the character's images folder. Returns the image URL.",
    "copy_file": "copy_file(src, dst): Copies a file from src to dst.",
    "update_engine_registry": "update_engine_registry(): Automatically registers all .narrat files in the engine's script folder.",
    "sync_narrat_config": "sync_narrat_config(): Scans scripts and automatically adds missing characters, screens, items, and quests to YAML configs.",
    "store_memory": "store_memory(text, type='chat', subject=None, relation=None, obj=None): Store a specific fact, chat snippet, or relationship in long-term memory.",
    "search_memory": "search_memory(query): Retrieves all relevant facts, chat logs, and relationships from memory.",
    "ask_memory": "ask_memory(question): Asks the memory a specific question and gets a synthesized answer.",
    "get_character_info": "get_character_info(character_name): Gets full character persona/card details from the Character Manager.",
    "search_character_images": "search_character_images(character_name, query=''): Searches the character's existing photo library for matching images.",
    "big_brain_query": "big_brain_query(prompt): Consults the high-brain API Service for complex technical or reasoning questions.",
    "send_user_response": "send_user_response(request_id, message): Pushes the final processed response back to the user frontend. Use this as the LAST step.",
    "generate_voice": "generate_voice(text, character='Anya'): Generates a voice audio file. ONLY use this if the user explicitly asks for 'voice generation' or 'TTS' (e.g. from the frontend audio button). Do NOT use this for standard chat responses.",
    "read_lifesim": "read_lifesim(character_name, target_day=None): Reads the character's schedule. If target_day is None, returns current context. Use this to know what you are doing right now.",
    "create_lifesim": "create_lifesim(character_name): Generates a new 7-day schedule for the character.",
    "change_lifesim": "change_lifesim(character_name, day, start_time, end_time, new_activity, details): Overwrites a schedule block. Use this if the user makes plans with you."
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
        self.provider = self.config.get("provider", None) # 'api' or 'local'
        self.model = self.config.get("model", None) # specific model name
        self.allowed_tools = self.config.get("tools", [])
        self.orchestrator = orchestrator
        self.current_request_id = None
        self.current_character = None

        # Shared namespace for Writing and Lore consistency
        self.memory_namespace = self.name
        if self.name in ["writer", "lore_checker"]:
            self.memory_namespace = "writer_lore_shared"
        
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
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.ui_logs.append({"type": msg_type, "content": f"[{timestamp}] {content}"})
        self.save_persistence()
        
    def get_logs(self):
        return self.ui_logs

    def process_queue(self):
        """Processes tasks with support for interrupts and mid-loop corrections."""
        if self.msg_queue.empty():
            return False
            
        print(f"DEBUG: [Agent {self.name}] Picking up task from queue...")
        self.is_working = True
        self.interrupt_flag = False
        task = self.msg_queue.get()
        sender, message = task.get("sender", "System"), task.get("message", "")
        
        # Try to extract request_id if it's a JSON string
        try:
            data = json.loads(message)
            if isinstance(data, dict):
                if "request_id" in data:
                    self.current_request_id = data["request_id"]
                if "character" in data:
                    self.current_character = data["character"]
                    # Override memory namespace to match the character identity
                    self.memory_namespace = self.current_character
        except:
            pass

        # We skip log_ui here because the server already logged the arrival
        self.memory.add_message("user", f"Message from {sender}: {message}")
        self.save_persistence()
        
        while True:
            if self.interrupt_flag:
                self.log_ui("error", "Task interrupted by user.")
                break

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
            
            # Real-time status update
            self.log_ui("thought", f"Sending prompt to {self.provider or 'default'} LLM...")
            
            response = self.api.call_llm(messages, provider=self.provider, model=self.model)
            
            if "error" in response:
                self.log_ui("error", response['error'])
                break
                
            thought = response.get("thought", "Thinking...")
            self.log_ui("thought", thought)
            
            if "tool_call" in response:
                import time
                tool_data = response["tool_call"]
                t_name, t_args = tool_data["name"], tool_data.get("args", {})
                self.log_ui("tool", f"Executing {t_name}...")
                
                start_tool = time.time()
                try:
                    # ... logic ...
                    if t_name == "update_scratchpad":
                        result = self.memory.update_scratchpad(t_args.get("text", ""))
                    elif t_name == "delegate_task":
                        target, msg = t_args.get("agent_name"), t_args.get("message")
                        
                        # Wrap message in JSON if we have a request_id
                        if self.current_request_id:
                            msg_payload = {
                                "request_id": self.current_request_id,
                                "message": msg
                            }
                            if self.current_character:
                                msg_payload["character"] = self.current_character
                            msg = json.dumps(msg_payload)
                            
                        if self.orchestrator.send_message(self.name, target, msg):
                            result = f"Task delegated to {target}."
                        else:
                            result = f"Error: Target agent '{target}' not found."
                    elif t_name == "read_file" and "read_file" in self.allowed_tools: result = read_file(**t_args)
                    elif t_name == "write_file" and "write_file" in self.allowed_tools: result = write_file(**t_args)
                    elif t_name == "list_dir" and "list_dir" in self.allowed_tools: result = list_dir(**t_args)
                    elif t_name == "web_search" and "web_search" in self.allowed_tools: result = web_search(**t_args)
                    elif t_name == "fetch_url" and "fetch_url" in self.allowed_tools: result = fetch_url(**t_args)
                    elif t_name == "send_notification" and "send_notification" in self.allowed_tools: result = send_notification(**t_args)
                    elif t_name == "generate_art" and "generate_art" in self.allowed_tools: result = generate_art(**t_args)
                    elif t_name == "copy_file" and "copy_file" in self.allowed_tools: result = copy_file(**t_args)
                    elif t_name == "update_engine_registry" and "update_engine_registry" in self.allowed_tools: result = update_engine_registry()
                    elif t_name == "sync_narrat_config" and "sync_narrat_config" in self.allowed_tools: result = sync_narrat_config()
                    elif t_name == "validate_narrat_scripts" and "validate_narrat_scripts" in self.allowed_tools: result = validate_narrat_scripts()
                    elif t_name == "store_memory" and "store_memory" in self.allowed_tools: result = store_memory(**t_args, namespace=self.memory_namespace)
                    elif t_name == "search_memory" and "search_memory" in self.allowed_tools: result = search_memory(**t_args, namespace=self.memory_namespace)
                    elif t_name == "ask_memory" and "ask_memory" in self.allowed_tools: result = ask_memory(**t_args, namespace=self.memory_namespace)
                    elif t_name == "get_character_info" and "get_character_info" in self.allowed_tools: result = get_character_info(**t_args)
                    elif t_name == "search_character_images" and "search_character_images" in self.allowed_tools: result = search_character_images(**t_args)
                    elif t_name == "big_brain_query" and "big_brain_query" in self.allowed_tools: result = big_brain_query(**t_args)
                    elif t_name == "send_user_response" and "send_user_response" in self.allowed_tools:
                        # Auto-fill request_id and character from context if missing
                        if "request_id" not in t_args and self.current_request_id:
                            t_args["request_id"] = self.current_request_id
                        if "character" not in t_args:
                            t_args["character"] = self.current_character or "Anya"
                        result = send_user_response(**t_args)
                    elif t_name == "generate_voice" and "generate_voice" in self.allowed_tools: result = generate_voice(**t_args)
                    elif t_name == "read_lifesim" and "read_lifesim" in self.allowed_tools: result = read_lifesim(**t_args)
                    elif t_name == "create_lifesim" and "create_lifesim" in self.allowed_tools: result = create_lifesim(**t_args)
                    elif t_name == "change_lifesim" and "change_lifesim" in self.allowed_tools: result = change_lifesim(**t_args)
                    else:
                        result = f"Error: Tool {t_name} not found or not permitted for this agent."
                except Exception as e:
                    result = f"Error executing tool {t_name}: {str(e)}"
                
                duration = time.time() - start_tool
                self.log_ui("result", f"Result ({duration:.2f}s): {str(result)}")
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
