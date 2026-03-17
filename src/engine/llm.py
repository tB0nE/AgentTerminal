import json
import requests
from config.settings import API_KEY, BASE_URL, MODEL_NAME

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
        
        try:
            response = requests.post(BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data['choices'][0]['message']['content']
            return json.loads(content)
        except Exception as e:
            return {"error": str(e)}
