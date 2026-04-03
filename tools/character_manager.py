import requests
import os
import sys

# Try modular import first
try:
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    from am_character_api.engine import manager as char_manager
    HAS_CHAR_MODULE = True
except ImportError:
    HAS_CHAR_MODULE = False

def get_character_info(character_name):
    """
    Queries the am_character_api (as a module or API) for full details.
    """
    if HAS_CHAR_MODULE:
        info = char_manager.get_character_info(character_name)
        if info: return info
        return {"error": f"Character {character_name} not found via module."}
    
    # Fallback to HTTP
    port = os.getenv("CHARACTER_MANAGER_PORT", "6923")
    url = f"http://localhost:{port}/api/characters/{character_name}/info"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": f"Failed to get character info via HTTP: {str(e)}"}

def search_character_images(character_name, query=""):
    """
    Searches the character's image library for existing photos matching a query.
    """
    if HAS_CHAR_MODULE:
        char_path = char_manager.get_character_path(character_name)
        img_dir = char_path / "images"
        if not img_dir.exists(): return "No images found."
        
        results = []
        # Find all .txt files (metadata)
        for txt_file in img_dir.glob("*.txt"):
            content = txt_file.read_text(encoding="utf-8").lower()
            if not query or query.lower() in content:
                filename = txt_file.stem + ".png"
                if (img_dir / filename).exists():
                    results.append({
                        "filename": filename,
                        "description": content[:100] + "...",
                        "url": f"/character-images/{character_name}/images/{filename}"
                    })
        
        if not results: return f"No existing images matching '{query}' found."
        return results[:10] # Return top 10 matches
    
    return "Error: am_character_api module not available for local search."

def big_brain_query(prompt):
    """
    Consults the high-brain API Service for complex technical or reasoning questions.
    """
    import sys
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
        
    from am_llm_api.engine import call_llm
    
    messages = [{"role": "user", "content": f"Please analyze this complex task: {prompt}"}]
    # We use a high-brain model (default from config)
    result = call_llm(messages, json_mode=False)
    
    if "error" in result:
        return f"Big Brain Error: {result['error']}"
    return result.get("content", "No response from big brain.")
