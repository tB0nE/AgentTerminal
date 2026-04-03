import os
import sys
import json
from config.settings import COMFYUI_URL

# Try modular import
try:
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    from am_comfyui.engine import get_engine
    HAS_COMFY_MODULE = True
except ImportError:
    HAS_COMFY_MODULE = False

def generate_art(prompt: str, workflow_name: str = "Donut_Standard.json", character: str = "Anya") -> str:
    """
    Generates an image using ComfyUI and saves it to the character's images folder.
    """
    if not HAS_COMFY_MODULE:
        return "Error: am_comfyui module not found."

    engine = get_engine()
    
    options = {
        "workflow": workflow_name,
        "width": 1024,
        "height": 1024
    }
    
    try:
        image_data = engine.generate_image(prompt, options)
        
        # Save to character directory
        from am_character_api.engine import manager as char_manager
        char_path = char_manager.get_character_path(character)
        images_dir = char_path / "images"
        images_dir.mkdir(exist_ok=True)
        
        import time
        filename = f"gen_{int(time.time())}.png"
        file_path = images_dir / filename
        
        with open(file_path, "wb") as f:
            f.write(image_data)
            
        # Save the prompt to a .txt file for metadata retrieval
        prompt_path = file_path.with_suffix('.txt')
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt)
            
        # Return a message that includes the path for other agents/frontend
        image_url = f"/character-images/{character}/images/{filename}"
        return f"Success! Image generated and saved. URL: {image_url}. Please notify the user that you've generated an image."
        
    except Exception as e:
        return f"Error during image generation: {str(e)}"

# Export for dynamic discovery
TOOL_DISPATCH = {
    "generate_art": generate_art
}
