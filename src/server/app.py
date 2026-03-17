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
    target_agent = data.get("agent")
    message = data.get("message", "")
    sender = data.get("sender", "ExternalApp")
    
    if not target_agent:
        return {"error": "Missing 'agent' field in payload"}
        
    success = _orchestrator_ref.send_message(sender, target_agent, message)
    if success:
        return {"status": f"Message sent to {target_agent}"}
    return {"error": f"Agent {target_agent} not found"}

def start_server(orchestrator):
    init_app(orchestrator)
    thread = threading.Thread(
        target=lambda: uvicorn.run(app, host="127.0.0.1", port=SERVER_PORT, log_level="error"),
        daemon=True
    )
    thread.start()
    return thread
