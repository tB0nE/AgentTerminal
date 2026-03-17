import asyncio
from src.engine.orchestrator import Orchestrator
from src.server.app import start_server
from src.ui.app import UIApp

async def main():
    print("Initializing Multi-Agent Studio...")
    
    # 1. Start the core engine (loads agents, starts background workers)
    orchestrator = Orchestrator()
    
    # 2. Start the external communication server
    start_server(orchestrator)
    
    # 3. Start the UI loop
    ui = UIApp(orchestrator)
    await ui.run_async()
    
    # Shutdown
    orchestrator.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
