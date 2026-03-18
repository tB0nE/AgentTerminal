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
        
        # Background worker thread
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def load_agents(self):
        """Discovers and instantiates all agents defined by JSON files."""
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
        while self.running:
            did_work = False
            for agent in self.agents.values():
                if agent.process_queue():
                    did_work = True
            
            if not did_work:
                time.sleep(0.5)

    def shutdown(self):
        self.running = False
