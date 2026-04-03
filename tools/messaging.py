import requests
import os
import sys

# Add root to path for modular imports
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if ROOT not in sys.path:
    sys.path.append(ROOT)

def send_user_response(request_id, message, character="Anya"):
    """
    Sends the final processed response back to the am_character_api callback endpoint.
    """
    port = os.getenv("CHARACTER_MANAGER_PORT", "6923")
    url = f"http://127.0.0.1:6924/api/internal/callback"
    
    payload = {
        "request_id": request_id,
        "content": message,
        "character": character
    }
    
    try:
        # --- NEW: Store bot's reply in memory too ---
        from tools.memory import store_memory
        store_memory(
            text=f"Assistant: {message}",
            namespace=character,
            type="chat"
        )
    except: pass

    try:
        print(f"\nDEBUG: [Messaging Tool] Pushing response for ID {request_id} to {url}")
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return "Response successfully pushed to frontend."
    except Exception as e:
        return f"Error pushing response to frontend: {str(e)}"
