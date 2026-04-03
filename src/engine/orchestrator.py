import os
import glob
import threading
import time
import sys
from src.engine.agent import Agent

# Modular imports for am_life_sim and am_character_api
try:
    # src/engine/orchestrator.py -> 3 levels up to AgenticMaster root
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "../../../"))
    if ROOT_DIR not in sys.path:
        sys.path.append(ROOT_DIR)
    from am_life_sim.engine import engine as lifesim
    from am_character_api.engine import manager as char_manager
    HAS_LIFESIM = True
except ImportError:
    HAS_LIFESIM = False

class Orchestrator:
    """
    The 'Central Brain' of the studio. 
    Manages the lifecycle of multiple agents and orchestrates background task execution.
    """
    def __init__(self, agents_dir: str = "agents"):
        self.agents_dir = agents_dir
        self.agents = {} # Map of agent_name -> Agent instance
        self.running = True
        self.load_agents()
        
        # Background worker thread for Agent processing
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

        # Background ticker for am_life_sim stats
        if HAS_LIFESIM:
            self.lifesim_thread = threading.Thread(target=self._lifesim_loop, daemon=True)
            self.lifesim_thread.start()

    def _lifesim_loop(self):
        """Background loop to update character stats every 5 minutes."""
        print(f"DEBUG: [Orchestrator] am_life_sim ticker started.")
        while self.running:
            try:
                characters = char_manager.get_available_characters()
                for char in characters:
                    lifesim.update_character_stats(char)
            except Exception as e:
                print(f"❌ [Orchestrator am_life_sim] Error: {e}")
            
            # Sleep for 5 minutes (or until shutdown)
            for _ in range(300):
                if not self.running: break
                time.sleep(1)

    def load_agents(self):
        """Discovers and instantiates all agents defined by JSON files."""
        self.agents.clear()
        if not os.path.exists(self.agents_dir):
            return
            
        for config_file in glob.glob(os.path.join(self.agents_dir, "*.json")):
            agent = Agent(config_file, self)
            self.agents[agent.name] = agent

    @property
    def llm(self):
        """Returns the LLMManager instance from one of the agents (they share a singleton)."""
        if self.agents:
            return list(self.agents.values())[0].api
        return None

    def get_agent(self, name: str):
        return self.agents.get(name)

    def send_message(self, sender: str, target: str, message: str):
        """
        Pushes a message to the target agent's queue.
        If the agent is already working, this acts as an 'Interjection'.
        """
        agent = self.get_agent(target)
        if agent:
            if agent.is_working:
                # Direct interjection into the current loop's memory
                agent.interjection_queue.put({"sender": sender, "message": message})
            else:
                # Standard task queue
                agent.msg_queue.put({"sender": sender, "message": message})
            return True
        return False

    def stop_agent(self, name: str):
        """Sets an interrupt flag for the specified agent."""
        agent = self.get_agent(name)
        if agent:
            agent.interrupt_flag = True
            return True
        return False

    def _worker_loop(self):
        """Background loop to process agent tasks."""
        print(f"DEBUG: [Orchestrator] Worker loop started.")
        while self.running:
            did_work = False
            for name, agent in self.agents.items():
                if agent.process_queue():
                    print(f"DEBUG: [Orchestrator] Agent {name} processed a task.")
                    did_work = True
            
            if not did_work:
                time.sleep(0.5)

    def shutdown(self):
        self.running = False
