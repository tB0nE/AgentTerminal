import time
import json
import os
import asyncio
import threading
import sys
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys
from prompt_toolkit.mouse_events import MouseEventType
import questionary
from tools.file_io import TOOL_DISPATCH as file_tools
from tools.research import TOOL_DISPATCH as research_tools
from tools.system import TOOL_DISPATCH as system_tools
from tools.comfy_api import TOOL_DISPATCH as comfy_tools

console = Console()
STATE_FILE = "config/state.json"

class UIApp:
    """
    The Terminal User Interface (TUI) layer.
    Optimized for screen space: Top agent bar, Bottom command/input area.
    """
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.active_agent = self.load_active_agent() # Load from persistence
        self.running = True
        self.input_buffer = "" 
        self.cursor_pos = 0   
        self.last_update = 0
        
        # UI State
        self.mode = "input" 
        self.menu_idx = 0    
        self.menu_options = ["Create Agent", "Edit Agent", "Back", "Exit"]
        
        # Scrolling State
        self.scroll_offsets = {name: 0 for name in orchestrator.agents.keys()}
        
        # Cursor Blinking State
        self.cursor_visible = True
        self.last_blink = time.time()

    def load_active_agent(self) -> str:
        """Loads the last used agent from state.json."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)
                    name = state.get("active_agent")
                    if name in self.orchestrator.agents:
                        return name
            except: pass
        return "writer" # default fallback

    def save_active_agent(self):
        """Saves the current active agent to state.json."""
        os.makedirs("config", exist_ok=True)
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump({"active_agent": self.active_agent}, f)
        except: pass

    def set_active_agent(self, name: str):
        """Updates the active agent and persists the state."""
        self.active_agent = name
        self.scroll_offsets[name] = 0
        self.save_active_agent()

    def make_layout(self) -> Layout:
        """Defines the optimized layout."""
        layout = Layout(name="root")
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="bottom", size=6)
        )
        return layout

    def render_header(self) -> Panel:
        """Renders the top agent bar with correctly processed markup."""
        agent_names = list(self.orchestrator.agents.keys())
        header_text = Text()
        
        for i, name in enumerate(agent_names):
            agent = self.orchestrator.agents[name]
            num_prefix = f"{i+1}-" if i < 9 else ""
            label = f"{num_prefix}{name}"
            
            if name == self.active_agent:
                header_text.append(f" {label} ", style="bold black on magenta")
            else:
                header_text.append(f" {label} ", style="bold white")
            
            if agent.is_working:
                header_text.append("(Working)", style="italic green")
            
            header_text.append("  ")
            
        return Panel(header_text, title="Agents (TAB / Ctrl+Num)", border_style="magenta")

    def render_chat_log(self) -> Panel:
        """Renders the main center panel."""
        agent = self.orchestrator.get_agent(self.active_agent)
        if not agent:
            return Panel("Agent not found.", title=f"Chat: {self.active_agent}")
            
        logs = agent.get_logs()
        full_text = Text()
        
        for log in logs[-150:]:
            t, c = log['type'], log['content']
            if t == "user": full_text.append(f"Task: {c}\n", style="bold yellow")
            elif t == "thought": full_text.append(f"Thought: {c}\n", style="magenta")
            elif t == "tool": full_text.append(f"Action: {c}\n", style="blue")
            elif t == "result": full_text.append(f"Result: {c}\n", style="dim green")
            elif t == "final": full_text.append(f"Final: {c}\n", style="bold cyan")
            elif t == "error": full_text.append(f"Error: {c}\n", style="bold red")
            full_text.append("\n")

        lines = full_text.split('\n')
        total_lines = len(lines)
        available_height = console.height - 3 - 6 - 2
        if available_height < 1: available_height = 10
        
        offset = self.scroll_offsets.get(self.active_agent, 0)
        
        if total_lines > available_height:
            end = total_lines - offset
            start = max(0, end - available_height)
            if start == 0: end = min(total_lines, available_height)
            display_lines = lines[start:end]
            scroll_indicator = f" [Scroll: {offset}]" if offset > 0 else " [Bottom]"
        else:
            display_lines = lines
            scroll_indicator = ""
            self.scroll_offsets[self.active_agent] = 0

        display_text = Text("\n").join(display_lines)
        return Panel(display_text, title=f"Agent: {self.active_agent}{scroll_indicator}", border_style="blue")

    def render_bottom(self) -> Panel:
        """Renders the bottom interactive area."""
        if self.mode == "menu":
            menu_text = Text()
            for i, opt in enumerate(self.menu_options):
                if i == self.menu_idx:
                    menu_text.append(f" > {opt} ", style="bold black on yellow")
                else:
                    menu_text.append(f"   {opt} ", style="white")
                menu_text.append("  ")
            return Panel(menu_text, title="System Menu", border_style="green")
        else:
            input_display = Text("> ")
            before = self.input_buffer[:self.cursor_pos]
            after = self.input_buffer[self.cursor_pos:]
            
            input_display.append(before)
            if self.cursor_visible:
                char_at_cursor = after[0] if after else " "
                input_display.append(char_at_cursor, style="bold black on white")
                input_display.append(after[1:])
            else:
                input_display.append(after)
                
            return Panel(
                input_display, 
                title=f"Input: {self.active_agent}", 
                subtitle="/menu: Options | /stop: Kill | /quit: Exit",
                border_style="cyan"
            )

    def get_renderable(self):
        layout = self.make_layout()
        layout["header"].update(self.render_header())
        layout["main"].update(self.render_chat_log())
        layout["bottom"].update(self.render_bottom())
        return layout

    async def handle_menu_action(self, live):
        """Performs operations asynchronously to avoid event loop conflicts."""
        opt = self.menu_options[self.menu_idx]
        if opt == "Exit":
            self.running = False
        elif opt == "Back":
            self.mode = "input"
        elif opt == "Create Agent" or opt == "Edit Agent":
            sys.stdout.write("\x1b[?1000l\x1b[?1006l")
            sys.stdout.flush()
            live.stop()
            
            # COMBINE ALL TOOLS for discovery
            available_tools = sorted(list(set(
                list(file_tools.keys()) + 
                list(research_tools.keys()) + 
                list(system_tools.keys()) + 
                list(comfy_tools.keys()) + 
                ["delegate_task", "update_scratchpad"]
            )))

            if opt == "Create Agent":
                name = await questionary.text("Agent Name:").ask_async()
                role_prompt = await questionary.text("Role Prompt:").ask_async()
                if name and role_prompt:
                    selected_tools = await questionary.checkbox(
                        "Select Tools:",
                        choices=[questionary.Choice(t, checked=(t in ["delegate_task", "update_scratchpad"])) for t in available_tools]
                    ).ask_async()
                    if selected_tools is not None:
                        config = {"name": name, "role": role_prompt, "tools": selected_tools}
                        with open(f"agents/{name}.json", 'w') as f: json.dump(config, f, indent=2)
                        self.orchestrator.load_agents()
                        if name not in self.scroll_offsets: self.scroll_offsets[name] = 0
            else:
                agents = list(self.orchestrator.agents.keys())
                target = await questionary.select("Edit agent:", choices=agents).ask_async()
                if target:
                    agent = self.orchestrator.get_agent(target)
                    new_role = await questionary.text("New Role Prompt:", default=agent.role).ask_async()
                    new_tools = await questionary.checkbox(
                        "Update Tools:",
                        choices=[questionary.Choice(t, checked=(t in agent.allowed_tools)) for t in available_tools]
                    ).ask_async()
                    if new_role and new_tools is not None:
                        agent.config["role"] = new_role
                        agent.config["tools"] = new_tools
                        with open(f"agents/{target}.json", 'w') as f: json.dump(agent.config, f, indent=2)
                        self.orchestrator.load_agents()
            
            live.start()
            sys.stdout.write("\x1b[?1000h\x1b[?1006h")
            sys.stdout.flush()
            self.mode = "input"

    async def run_async(self):
        input_obj = create_input()
        try:
            with Live(self.get_renderable(), screen=True, auto_refresh=False) as live:
                sys.stdout.write("\x1b[?1000h\x1b[?1006h"); sys.stdout.flush()
                with input_obj.raw_mode():
                    while self.running:
                        if time.time() - self.last_blink > 0.5:
                            self.cursor_visible = not self.cursor_visible; self.last_blink = time.time(); live.update(self.get_renderable()); live.refresh()
                        if time.time() - self.last_update > 0.1:
                            live.update(self.get_renderable()); live.refresh(); self.last_update = time.time()
                        keys = input_obj.read_keys()
                        if not keys: await asyncio.sleep(0.02); continue
                        for key in keys:
                            if hasattr(key, 'mouse_event'):
                                me = key.mouse_event
                                if me.event_type == MouseEventType.SCROLL_UP: self.scroll_offsets[self.active_agent] += 2
                                elif me.event_type == MouseEventType.SCROLL_DOWN: self.scroll_offsets[self.active_agent] = max(0, self.scroll_offsets[self.active_agent] - 2)
                                continue
                            if key.key in [Keys.Backspace, Keys.ControlH, "\x7f", "\x08"]:
                                if self.mode == "input" and self.cursor_pos > 0:
                                    self.input_buffer = self.input_buffer[:self.cursor_pos-1] + self.input_buffer[self.cursor_pos:]
                                    self.cursor_pos -= 1
                                continue
                            if key.key == Keys.Tab:
                                agents = list(self.orchestrator.agents.keys()); curr_idx = agents.index(self.active_agent)
                                self.set_active_agent(agents[(curr_idx + 1) % len(agents)]); continue
                            elif key.key == Keys.BackTab:
                                agents = list(self.orchestrator.agents.keys()); curr_idx = agents.index(self.active_agent)
                                self.set_active_agent(agents[(curr_idx - 1) % len(agents)]); continue
                            ctrl_nums = {Keys.ControlA: 0, Keys.ControlB: 1, Keys.ControlC: 2, Keys.ControlD: 3, Keys.ControlE: 4, Keys.ControlF: 5, Keys.ControlG: 6, Keys.ControlH: 7, Keys.ControlI: 8}
                            if key.key in ctrl_nums:
                                idx = ctrl_nums[key.key]; agents = list(self.orchestrator.agents.keys())
                                if idx < len(agents): self.set_active_agent(agents[idx])
                                continue
                            if key.key == Keys.Left:
                                if self.mode == "menu": self.menu_idx = (self.menu_idx - 1) % len(self.menu_options)
                                else: self.cursor_pos = max(0, self.cursor_pos - 1)
                            elif key.key == Keys.Right:
                                if self.mode == "menu": self.menu_idx = (self.menu_idx + 1) % len(self.menu_options)
                                else: self.cursor_pos = min(len(self.input_buffer), self.cursor_pos + 1)
                            elif key.key == Keys.Up: self.scroll_offsets[self.active_agent] += 2
                            elif key.key == Keys.Down: self.scroll_offsets[self.active_agent] = max(0, self.scroll_offsets[self.active_agent] - 2)
                            elif key.key == Keys.Enter or key.key == Keys.ControlM:
                                if self.mode == "input":
                                    cmd = self.input_buffer.strip(); self.input_buffer = ""; self.cursor_pos = 0
                                    if cmd == "/quit": self.running = False
                                    elif cmd == "/stop": self.orchestrator.stop_agent(self.active_agent)
                                    elif cmd == "/menu": self.mode = "menu"; self.menu_idx = 0
                                    elif cmd: self.orchestrator.send_message("User", self.active_agent, cmd); self.scroll_offsets[self.active_agent] = 0
                                else: await self.handle_menu_action(live)
                            elif self.mode == "input":
                                if isinstance(key.key, str) and len(key.key) == 1:
                                    self.input_buffer = self.input_buffer[:self.cursor_pos] + key.key + self.input_buffer[self.cursor_pos:]
                                    self.cursor_pos += 1
                                elif key.key == " ": 
                                    self.input_buffer = self.input_buffer[:self.cursor_pos] + " " + self.input_buffer[self.cursor_pos:]
                                    self.cursor_pos += 1
                            if key.key == Keys.ControlC: self.running = False; break
                        live.update(self.get_renderable()); live.refresh()
        finally:
            sys.stdout.write("\x1b[?1000l\x1b[?1006l"); sys.stdout.flush()
