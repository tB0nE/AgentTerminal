import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
MODEL_NAME = os.getenv("MODEL_NAME", "glm-4-flash")
SERVER_PORT = int(os.getenv("SERVER_PORT", "5112"))
AUTO_LORE_CHECK = os.getenv("AUTO_LORE_CHECK", "true").lower() == "true"
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")
