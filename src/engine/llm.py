import os
import json
import sys
import requests
from config.settings import API_KEY, BASE_URL, MODEL_NAME
from src.utils.logger import log_debug, log_error

# Modular imports
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    from am_llm_api.engine import APIHandler as ModularAPIHandler
    HAS_API_MODULE = True
except ImportError:
    HAS_API_MODULE = False

try:
    from am_llm_local.engine import am_llm_localEngine
    HAS_LOCAL_MODULE = True
except ImportError:
    HAS_LOCAL_MODULE = False

# Global instances for singleton behavior
_global_api_handler = None
_global_local_engine = None

class LLMManager:
    def __init__(self):
        global _global_api_handler, _global_local_engine
        
        self.use_api_module = HAS_API_MODULE and os.getenv("USE_MODULAR_API", "true").lower() == "true"
        self.use_local_module = HAS_LOCAL_MODULE and os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
        
        if self.use_api_module and _global_api_handler is None:
            _global_api_handler = ModularAPIHandler(
                api_key=API_KEY,
                base_url=BASE_URL,
                model_name=MODEL_NAME
            )
        self.api_handler = _global_api_handler
        
        if self.use_local_module and _global_local_engine is None:
            print("\n\033[93m[SYSTEM] Loading Local LLM Model (this may take a moment)... \033[0m")
            _global_local_engine = am_llm_localEngine()
            # Trigger lazy load now so it's ready for first use
            _ = _global_local_engine.model
            print("\033[92m[SYSTEM] Local LLM Model Loaded! \033[0m\n")
            
        self.local_engine = _global_local_engine
            
    def list_all_available_models(self) -> dict:
        """Returns a dict of all available providers and their models."""
        results = {"api": {}, "local": []}
        
        if HAS_API_MODULE:
            results["api"] = self.api_handler.get_available_providers()
            
        if HAS_LOCAL_MODULE:
            # Need an instance to call list_available_models if not loaded yet
            temp_engine = _global_local_engine or am_llm_localEngine()
            results["local"] = temp_engine.list_available_models()
            
        return results

    def call_llm(self, messages: list, provider: str = None, model: str = None) -> dict:
        """
        Calls an LLM. 
        provider can be 'api' or 'local'.
        model is the specific model name/filename.
        """
        global _global_local_engine
        
        # 1. Determine initial provider
        requested_provider = provider or ("local" if self.use_local_module else "api")
            
        # 2. Case: Local Provider
        if requested_provider == "local" and HAS_LOCAL_MODULE:
            return self._call_local(messages, model)
            
        # 3. Case: API Provider (with automatic local fallback)
        if self.use_api_module:
            api_provider = requested_provider if requested_provider in self.api_handler.providers else None
            print(f"\n\033[92m[DEBUG] Using API Service ({api_provider or 'default'}) - Model: {model or 'default'}\033[0m")
            
            result = self.api_handler.call_llm(messages, provider_id=api_provider, model_name=model)
            
            # CHECK FOR FAILURE (Error or JSON Parse Error)
            is_error = "error" in result
            is_parse_fail = is_error and "JSON parse error" in str(result["error"])
            
            if is_error or is_parse_fail:
                if HAS_LOCAL_MODULE:
                    print(f"\n\033[91m[⚠️ WARNING] API Failed: {result.get('error')}\033[0m")
                    print(f"\033[93m[🔄 FALLBACK] Switching to Local LLM... \033[0m")
                    return self._call_local(messages, None) # Use default local model for fallback
                else:
                    print(f"\n\033[91m[❌ CRITICAL] API Failed and no Local LLM available.\033[0m")
            
            return result
        
        # Legacy fallback
        return {"error": "No LLM provider available"}

    def _call_local(self, messages: list, model: str = None) -> dict:
        """Internal helper to handle local LLM calls."""
        global _global_local_engine
        if _global_local_engine is None:
            print("\n\033[93m[SYSTEM] On-demand loading Local LLM Model... \033[0m")
            _global_local_engine = am_llm_localEngine()
        
        if model:
            success, msg = _global_local_engine.switch_model(model)
            if not success: return {"error": msg}
        
        self.local_engine = _global_local_engine
        print(f"\n\033[94m[DEBUG] Using Local LLM: {os.path.basename(self.local_engine.current_model_path)}\033[0m")
        
        system_msgs = [m['content'] for m in messages if m['role'] == 'system']
        user_history = [m for m in messages if m['role'] != 'system']
        system_prompt = "\n".join(system_msgs)
        
        prompt = f"System: {system_prompt}\n\n"
        for msg in user_history:
            role = "User" if msg['role'] == 'user' else "Assistant"
            prompt += f"{role}: {msg['content']}\n"
        prompt += "Assistant: "
        
        print(f"\033[90m[DEBUG] Local Prompt Length: {len(prompt)} chars\033[0m")
        return self.local_engine.generate_json(prompt)
        
        # Legacy fallback
        log_debug("Using direct HTTP LLM API (Legacy)")
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
            log_error(f"LLM API Error: {str(e)}")
            return {"error": str(e)}

# For backward compatibility with existing code that does: from src.engine.llm import APIHandler
class APIHandler(LLMManager):
    pass
