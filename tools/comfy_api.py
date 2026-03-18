import json
import urllib.request
import urllib.error
import urllib.parse
import os
import time
from config.settings import COMFYUI_URL

def generate_art(prompt: str, workflow_name: str, output_name: str = "generated_asset") -> str:
    """
    Loads a custom ComfyUI JSON workflow from the root 'workflows/' directory,
    injects the prompt and output filename, and triggers generation.
    """
    output_dir = "project/generated_art"
    workflow_path = os.path.join("workflows", f"{workflow_name}.json")
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(workflow_path):
        return f"Error: Workflow '{workflow_name}' not found in 'workflows/' directory."

    try:
        # 1. Load the custom JSON workflow
        with open(workflow_path, 'r', encoding='utf-8') as f:
            workflow = json.load(f)

        # 2. Template Injection Logic
        prompt_injected = False
        output_injected = False
        
        for node_id in workflow:
            node = workflow[node_id]
            class_type = node.get("class_type")
            
            if class_type == "CLIPTextEncode" and not prompt_injected:
                node["inputs"]["text"] = prompt
                prompt_injected = True
            
            if class_type == "SaveImage":
                node["inputs"]["filename_prefix"] = output_name
                output_injected = True
            
            if class_type == "KSampler":
                node["inputs"]["seed"] = int(time.time() * 1000) % 1125899906842624

        # 3. Queue Prompt
        payload = {"prompt": workflow}
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(f"{COMFYUI_URL}/prompt", data=data, headers={'Content-Type': 'application/json'})
        
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read())
            prompt_id = res_data.get("prompt_id")

        # 4. Poll for Completion
        max_attempts = 150 
        for _ in range(max_attempts):
            time.sleep(3)
            with urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}") as history_res:
                history = json.loads(history_res.read())
                
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node_id in outputs:
                    for img in outputs[node_id].get("images", []):
                        filename = img.get("filename")
                        subfolder = img.get("subfolder", "")
                        
                        img_url = f"{COMFYUI_URL}/view?filename={filename}&subfolder={subfolder}&type=output"
                        local_path = os.path.join(output_dir, f"{output_name}_{int(time.time())}.png")
                        
                        urllib.request.urlretrieve(img_url, local_path)
                        return f"Success! Used workflow '{workflow_name}'. Image saved to: {local_path}"
        
        return f"Timeout: Workflow '{workflow_name}' queued but not finished."
        
    except Exception as e:
        return f"Error during ComfyUI cycle: {str(e)}"

# Export for dynamic discovery
TOOL_DISPATCH = {
    "generate_art": generate_art
}
