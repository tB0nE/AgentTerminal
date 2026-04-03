import threading
from fastapi import FastAPI, Request
import uvicorn
from config.settings import SERVER_PORT

app = FastAPI()
_orchestrator_ref = None

def init_app(orchestrator):
    global _orchestrator_ref
    _orchestrator_ref = orchestrator

@app.post("/message")
async def receive_message(request: Request):
    if not _orchestrator_ref:
        return {"error": "Server not fully initialized"}
        
    data = await request.json()
    target_agent_name = data.get("agent")
    message = data.get("message", "")
    sender = data.get("sender", "ExternalApp")
    
    if not target_agent_name:
        return {"error": "Missing 'agent' field in payload"}
        
    agent = _orchestrator_ref.get_agent(target_agent_name)
    if agent:
        # Log to UI immediately
        agent.log_ui("user", f"[{sender}] {message}")
        
        # --- NEW: Automatic Memory Storage (Fire and Forget) ---
        def background_memory():
            try:
                import json
                import os
                import sys
                msg_data = json.loads(message)
                if isinstance(msg_data, dict) and "character" in msg_data and "user_message" in msg_data:
                    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
                    if ROOT not in sys.path: sys.path.append(ROOT)
                    from tools.memory import store_memory
                    store_memory(
                        text=f"User: {msg_data['user_message']}",
                        namespace=msg_data["character"],
                        type="chat"
                    )
            except: pass
        
        # Run memory storage in a separate thread to not block the response
        threading.Thread(target=background_memory, daemon=True).start()

        # Send to orchestrator queue
        _orchestrator_ref.send_message(sender, target_agent_name, message)
        
        # RETURN IMMEDIATELY
        return {"status": "accepted", "message": f"Task queued for {target_agent_name}"}
    
    return {"error": f"Agent {target_agent_name} not found"}

def start_server(orchestrator):
    init_app(orchestrator)
    thread = threading.Thread(
        target=lambda: uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT, log_level="error"),
        daemon=True
    )
    thread.start()
    return thread
