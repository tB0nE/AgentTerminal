import requests
import os
import sys

BASE_URL = "http://localhost:7087"

# --- MODULAR IMPORT ATTEMPT ---
try:
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    MM_PATH = os.path.join(ROOT, "am_memory")
    if MM_PATH not in sys.path:
        sys.path.append(MM_PATH)
    from app.memory.processor import processor as mm_processor
    from app.memory.vector import vector_db as mm_vector
    from app.memory.graph import graph_db as mm_graph
    HAS_LOCAL_MM = True
except ImportError:
    HAS_LOCAL_MM = False

def store_memory(text: str, namespace: str, type: str = "chat", subject: str = None, relation: str = None, obj: str = None):
    """Stores a memory in the Long-Term Memory API (or locally if available)."""
    if HAS_LOCAL_MM:
        try:
            if type == "chat":
                return mm_processor.process_chat(text, namespace=namespace)
            elif type == "fact":
                mm_vector.add_fact(text, namespace=namespace)
                return {"status": "success"}
            elif type == "relationship":
                mm_graph.add_relationship(subject, relation, obj, namespace=namespace)
                return {"status": "success"}
        except Exception as e:
            print(f"❌ [Local MM Error] {e}")

    # Fallback to HTTP
    try:
        if type == "chat":
            payload = {"text": text, "namespace": namespace}
            response = requests.post(f"{BASE_URL}/store/chat", json=payload, timeout=10)
        elif type == "fact":
            payload = {"content": text, "type": "fact", "namespace": namespace}
            response = requests.post(f"{BASE_URL}/store/targeted", json=payload, timeout=10)
        elif type == "relationship":
            content = text if text else f"{subject} {relation} {obj}"
            payload = {
                "content": content, "type": "relationship", "subject": subject,
                "relation": relation, "object": obj, "namespace": namespace
            }
            response = requests.post(f"{BASE_URL}/store/targeted", json=payload, timeout=10)
        else:
            return {"error": f"Invalid memory type: {type}"}
        
        if response.status_code != 200:
            print(f"⚠️ [Memory API Error] status={response.status_code}")
        
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ [Memory Tool Critical] {e}")
        return {"error": f"Failed to store memory: {str(e)}"}

def search_memory(query: str, namespace: str):
    """Retrieves all relevant facts, chat logs, and relationships."""
    if HAS_LOCAL_MM:
        try:
            return mm_processor.retrieve_all(query, namespace=namespace)
        except: pass

    try:
        payload = {"query": query, "namespace": namespace}
        response = requests.post(f"{BASE_URL}/retrieve/all", json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": f"Failed to search memory: {str(e)}"}

def ask_memory(question: str, namespace: str):
    """Asks the memory a specific question and gets a synthesized answer."""
    if HAS_LOCAL_MM:
        try:
            ans = mm_processor.retrieve_targeted(question, namespace=namespace)
            return {"answer": ans}
        except: pass

    try:
        payload = {"query": question, "namespace": namespace}
        response = requests.post(f"{BASE_URL}/retrieve/targeted", json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": f"Failed to ask memory: {str(e)}"}
