import os
import glob
import threading
import time
from src.engine.agent import Agent

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
        
        # Background worker thread: continuously polls all agents for work
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def load_agents(self):
        """Discovers and instantiates all agents defined by JSON files in the agents/ directory."""
        self.agents.clear()
        if not os.path.exists(self.agents_dir):
            return
            
        for config_file in glob.glob(os.path.join(self.agents_dir, "*.json")):
            agent = Agent(config_file, self)
            self.agents[agent.name] = agent

    def get_agent(self, name: str):
        return self.agents.get(name)

    def send_message(self, sender: str, target: str, message: str):
        """
        Directly injects a message into a specific agent's queue.
        Used for user interaction, inter-agent delegation, and external API calls.
        """
        agent = self.get_agent(target)
        if agent:
            agent.msg_queue.put({"sender": sender, "message": message})
            return True
        return False

    def _worker_loop(self):
        """
        Main background loop that gives CPU time to each agent.
        If an agent has items in its queue, it will start its ReAct cycle.
        """
        while self.running:
            did_work = False
            # Iterate through all loaded agents and see if they have pending tasks
            for agent in self.agents.values():
                if agent.process_queue():
                    did_work = True
            
            # Prevent high CPU usage when no work is pending
            if not did_work:
                time.sleep(0.5)

    def shutdown(self):
        """Stops the background worker thread."""
        self.running = False
