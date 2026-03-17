import json
import requests
from config.settings import API_KEY, BASE_URL, MODEL_NAME
from src.utils.logger import log_debug, log_error

class APIHandler:
    def __init__(self):
        if not API_KEY:
            raise ValueError("Missing API_KEY in .env")

    def call_llm(self, messages: list) -> dict:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": 0.7,
            "response_format": {"type": "json_object"}
        }
        
        log_debug(f"LLM Request Payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = requests.post(BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data['choices'][0]['message']['content']
            
            log_debug(f"LLM Response Content: {content}")
            return json.loads(content)
        except Exception as e:
            log_error(f"LLM API Error: {str(e)}")
            return {"error": str(e)}
