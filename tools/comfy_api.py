import json
import urllib.request
import urllib.error
import urllib.parse
from config.settings import COMFYUI_URL

def generate_art(prompt: str, output_name: str = "generated_asset") -> str:
    """
    Sends a prompt to a local ComfyUI instance to generate an image.
    Requires COMFYUI_URL in settings (default: http://127.0.0.1:8188).
    """
    try:
        # A basic ComfyUI workflow (Load Checkpoint -> Text Encode -> KSampler -> VAE Decode -> Save Image)
        # This is a highly simplified template. In a real setup, you'd load a specific JSON workflow file.
        workflow = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 8,
                    "denoise": 1,
                    "latent_image": ["5", 0],
                    "model": ["4", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "seed": 8566257,
                    "steps": 20
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "v1-5-pruned-emaonly.ckpt"} # Assume standard SD1.5 model is present
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"batch_size": 1, "height": 512, "width": 512}
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["4", 1], "text": prompt}
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["4", 1], "text": "bad quality, blurry, watermark"}
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]}
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": output_name, "images": ["8", 0]}
            }
        }

        payload = {"prompt": workflow}
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(f"{COMFYUI_URL}/prompt", data=data, headers={'Content-Type': 'application/json'})
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read())
            prompt_id = result.get("prompt_id")
            
        return f"Successfully queued image generation in ComfyUI. Prompt ID: {prompt_id}. Output prefix: {output_name}"
        
    except urllib.error.URLError as e:
        return f"Error connecting to ComfyUI at {COMFYUI_URL}. Is it running? Details: {e.reason}"
    except Exception as e:
        return f"Error during ComfyUI generation: {str(e)}"

# Export for dynamic discovery
TOOL_DISPATCH = {
    "generate_art": generate_art
}
