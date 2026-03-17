import time
import json
import os
import asyncio
import threading
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

console = Console()

class UIApp:
    """
    The Terminal User Interface (TUI) layer.
    Manages a split-screen dashboard and keyboard/mouse navigation.
    """
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.active_agent = "writer" 
        self.running = True
        self.input_buffer = "" 
        self.last_update = 0
        
        # Navigation State
        self.focus = "input" 
        self.agent_idx = 0   
        self.menu_idx = 0    
        self.menu_options = ["Create Agent", "Edit Agent", "Exit"]
        
        # Scrolling State (number of character lines to shift UP from the bottom)
        self.scroll_offsets = {name: 0 for name in orchestrator.agents.keys()}

    def make_layout(self) -> Layout:
        """Defines the 3-panel split screen structure."""
        layout = Layout(name="root")
        layout.split(
            Layout(name="main", ratio=8),
            Layout(name="footer", size=3)
        )
        layout["main"].split_row(
            Layout(name="left", ratio=7),
            Layout(name="right", ratio=3)
        )
        layout["right"].split_column(
            Layout(name="agents_list", ratio=1),
            Layout(name="menu_panel", ratio=1)
        )
        return layout

    def render_agents_list(self) -> Panel:
        """Renders the top-right list of agents with status indicators."""
        table = Table(show_header=True, header_style="bold magenta", expand=True, box=None)
        table.add_column("Agent")
        table.add_column("Status")
        
        agent_names = list(self.orchestrator.agents.keys())
        for i, name in enumerate(agent_names):
            agent = self.orchestrator.agents[name]
            status = "[bold green]Working[/bold green]" if agent.is_working else "[dim]Idle[/dim]"
            prefix = ">>" if name == self.active_agent else "  "
            display_name = f"{prefix} {name}"
            if self.focus == "agents" and i == self.agent_idx:
                display_name = f"[bold black on yellow] {display_name} [/bold black on yellow]"
            table.add_row(display_name, status)
            
        border_style = "bold green" if self.focus == "agents" else "magenta"
        return Panel(table, title="Agents (TAB to Focus)", border_style=border_style)

    def render_chat_log(self) -> Panel:
        """Renders the main left-hand panel with character-line scrolling."""
        agent = self.orchestrator.get_agent(self.active_agent)
        if not agent:
            return Panel("Agent not found.", title=f"Chat: {self.active_agent}")
            
        logs = agent.get_logs()
        full_text = Text()
        
        # Build the full formatted text block
        for log in logs[-100:]:
            t, c = log['type'], log['content']
            if t == "user": full_text.append(f"Task: {c}\n", style="bold yellow")
            elif t == "thought": full_text.append(f"Thought: {c}\n", style="magenta")
            elif t == "tool": full_text.append(f"Action: {c}\n", style="blue")
            elif t == "result": full_text.append(f"Result: {c}\n", style="dim green")
            elif t == "final": full_text.append(f"Final: {c}\n", style="bold cyan")
            elif t == "error": full_text.append(f"Error: {c}\n", style="bold red")
            full_text.append("\n")

        # Split into individual physical lines
        lines = full_text.split('\n')
        total_lines = len(lines)

        # Panel dimensions
        available_height = console.height - 3 - 2 - 2 
        if available_height < 1: available_height = 10
        
        offset = self.scroll_offsets.get(self.active_agent, 0)
        
        # Slice lines based on offset
        if total_lines > available_height:
            end = total_lines - offset
            start = max(0, end - available_height)
            
            # Ensure we always show a full screen if offset is large
            if start == 0:
                end = min(total_lines, available_height)
            
            display_lines = lines[start:end]
            scroll_indicator = f" [Scroll: {offset}]" if offset > 0 else " [Bottom]"
        else:
            display_lines = lines
            scroll_indicator = ""
            self.scroll_offsets[self.active_agent] = 0

        display_text = Text("\n").join(display_lines)
        return Panel(display_text, title=f"History: {self.active_agent}{scroll_indicator}", border_style="blue")

    def render_menu(self) -> Panel:
        """Renders the bottom-right list of system actions."""
        lines = []
        for i, opt in enumerate(self.menu_options):
            if self.focus == "menu" and i == self.menu_idx:
                lines.append(f"> [bold black on yellow] {opt} [/bold black on yellow]")
            else:
                lines.append(f"  {opt}")
        border_style = "bold green" if self.focus == "menu" else "green"
        return Panel("\n".join(lines), title="Menu (TAB to Focus)", border_style=border_style)

    def get_renderable(self):
        """Assembles all panels into the final Layout object."""
        layout = self.make_layout()
        layout["agents_list"].update(self.render_agents_list())
        layout["left"].update(self.render_chat_log())
        layout["menu_panel"].update(self.render_menu())
        
        input_style = "bold green" if self.focus == "input" else "cyan"
        input_display = f"[{self.active_agent}] > {self.input_buffer}"
        if self.focus == "input": input_display += "█"
        layout["footer"].update(Panel(input_display, title="Mouse Scroll: History", border_style=input_style))
        return layout

    def handle_menu_action(self, live):
        opt = self.menu_options[self.menu_idx]
        if opt == "Exit": self.running = False
        elif opt == "Create Agent" or opt == "Edit Agent":
            live.stop()
            if opt == "Create Agent":
                name = questionary.text("Name:").ask()
                role = questionary.text("Role:").ask()
                if name and role:
                    config = {"name": name, "role": role, "tools": ["read_file", "write_file", "delegate_task", "update_scratchpad"]}
                    with open(f"agents/{name}.json", 'w') as f: json.dump(config, f, indent=2)
                    self.orchestrator.load_agents()
            else:
                agents = list(self.orchestrator.agents.keys())
                target = questionary.select("Edit agent:", choices=agents).ask()
                if target:
                    agent = self.orchestrator.get_agent(target)
                    new_role = questionary.text("New Role:", default=agent.role).ask()
                    if new_role:
                        agent.config["role"] = new_role
                        with open(f"agents/{target}.json", 'w') as f: json.dump(agent.config, f, indent=2)
                        self.orchestrator.load_agents()
            live.start()

    async def run_async(self):
        input_obj = create_input()
        console.print("\x1b[?1000h\x1b[?1006h", end="")

        with Live(self.get_renderable(), screen=True, auto_refresh=False) as live:
            with input_obj.raw_mode():
                while self.running:
                    if time.time() - self.last_update > 0.1:
                        live.update(self.get_renderable()); live.refresh()
                        self.last_update = time.time()

                    keys = input_obj.read_keys()
                    if not keys:
                        await asyncio.sleep(0.02); continue
                    
                    for key in keys:
                        # --- GLOBAL MOUSE SCROLL ---
                        if hasattr(key, 'mouse_event'):
                            me = key.mouse_event
                            if me.event_type == MouseEventType.SCROLL_UP:
                                self.scroll_offsets[self.active_agent] += 2
                            elif me.event_type == MouseEventType.SCROLL_DOWN:
                                self.scroll_offsets[self.active_agent] = max(0, self.scroll_offsets[self.active_agent] - 2)
                            continue

                        # --- NAVIGATION ---
                        if key.key == Keys.Tab:
                            if self.focus == "input": self.focus = "agents"
                            elif self.focus == "agents": self.focus = "menu"
                            else: self.focus = "input"
                        
                        elif key.key == Keys.Up:
                            if self.focus == "agents":
                                self.agent_idx = (self.agent_idx - 1) % len(self.orchestrator.agents)
                                self.active_agent = list(self.orchestrator.agents.keys())[self.agent_idx]
                            elif self.focus == "menu":
                                self.menu_idx = (self.menu_idx - 1) % len(self.menu_options)
                            else:
                                self.scroll_offsets[self.active_agent] += 2

                        elif key.key == Keys.Down:
                            if self.focus == "agents":
                                self.agent_idx = (self.agent_idx + 1) % len(self.orchestrator.agents)
                                self.active_agent = list(self.orchestrator.agents.keys())[self.agent_idx]
                            elif self.focus == "menu":
                                self.menu_idx = (self.menu_idx + 1) % len(self.menu_options)
                            else:
                                self.scroll_offsets[self.active_agent] = max(0, self.scroll_offsets[self.active_agent] - 2)
                        
                        elif key.key == Keys.Enter or key.key == Keys.ControlM:
                            if self.focus == "input":
                                cmd = self.input_buffer.strip()
                                self.input_buffer = ""
                                if cmd == "/quit": self.running = False
                                elif cmd: 
                                    self.orchestrator.send_message("User", self.active_agent, cmd)
                                    self.scroll_offsets[self.active_agent] = 0
                            elif self.focus == "menu":
                                self.handle_menu_action(live)
                        
                        elif self.focus == "input":
                            if key.key == Keys.Backspace: self.input_buffer = self.input_buffer[:-1]
                            elif isinstance(key.key, str) and len(key.key) == 1: self.input_buffer += key.key
                            elif key.key == Keys.Space: self.input_buffer += " "
                        
                        elif key.key == Keys.ControlC:
                            self.running = False; break
                    
                    live.update(self.get_renderable()); live.refresh()

        console.print("\x1b[?1000l\x1b[?1006l", end="")
