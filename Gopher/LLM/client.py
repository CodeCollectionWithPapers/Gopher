import os
import time
import json
import logging
import requests
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Union
import yaml

logger = logging.getLogger(__name__)

class LLMError(Exception):
    pass

def retry_with_backoff(max_retries: int = 5, backoff_factor: float = 2.0):

    def decorator(func):
        def wrapper(*args, **kwargs):
            retry_count = 0
            delay = 1.0
            last_exception = None

            while retry_count < max_retries:
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.RequestException, LLMError) as e:
                    # Don't retry on client side errors (400-499) unless it's 429 (Rate Limit)
                    if isinstance(e, requests.exceptions.HTTPError):
                        status = e.response.status_code
                        if 400 <= status < 500 and status != 429:
                            logger.error(f"Non-retriable HTTP error: {status} - {e}")
                            raise e

                    last_exception = e
                    retry_count += 1
                    sleep_time = delay * (backoff_factor ** (retry_count - 1))
                    logger.warning(
                        f"LLM request failed: {e}. Retrying in {sleep_time:.2f}s (Attempt {retry_count}/{max_retries})...")
                    time.sleep(sleep_time)

            logger.error(f"Max retries reached. Last error: {last_exception}")
            raise last_exception

        return wrapper

    return decorator

class BaseLLMClient(ABC):

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_name = config.get("model_name", "unknown")
        self.temperature = config.get("temperature", 0.0)  # Default to 0 for deterministic repairs

    @abstractmethod
    def generate_completion(self, system_message: str, user_prompt: str) -> str:
        pass

class OpenAICompatibleClient(BaseLLMClient):

    def __init__(self, config: Dict[str, Any], api_key_env_var: str):
        super().__init__(config)
        self.api_key = os.getenv(api_key_env_var)
        self.base_url = config.get("base_url", "https://api.openai.com/v1")

        if not self.api_key:
            logger.warning(f"API Key environment variable '{api_key_env_var}' not set for {self.model_name}.")

    @retry_with_backoff()
    def generate_completion(self, system_message: str, user_prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.temperature,
            "n": 1
        }

        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"

        response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
        response.raise_for_status()

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise LLMError(f"Unexpected response format from {self.model_name}: {data}")

class GoogleGenAIClient(BaseLLMClient):

    def __init__(self, config: Dict[str, Any], api_key_env_var: str):
        super().__init__(config)
        self.api_key = os.getenv(api_key_env_var)
        self.base_url = config.get("base_url", "https://generativelanguage.googleapis.com/v1beta/models")

    @retry_with_backoff()
    def generate_completion(self, system_message: str, user_prompt: str) -> str:

        url = f"{self.base_url}/{self.model_name}:generateContent"
        params = {"key": self.api_key}
        headers = {"Content-Type": "application/json"}

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_message}]
            },
            "contents": [
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            "generationConfig": {
                "temperature": self.temperature
            }
        }

        response = requests.post(url, params=params, headers=headers, json=payload, timeout=60)

        if response.status_code != 200:
            logger.error(f"Gemini API Error: {response.text}")
            response.raise_for_status()

        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            # Check for safety blocks
            if "promptFeedback" in data and "blockReason" in data["promptFeedback"]:
                raise LLMError(f"Gemini blocked content: {data['promptFeedback']}")
            raise LLMError(f"Unexpected response format from Gemini: {data}")


class OllamaClient(BaseLLMClient):

    def __init__(self, config: Dict[str, Any], model_alias: str):

        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")

        models_map = config.get("models", {})
        self.actual_model_tag = models_map.get(model_alias, model_alias)

        self.options = config.get("options", {})

    @retry_with_backoff(max_retries=3, backoff_factor=1.5)  # Fewer retries for local
    def generate_completion(self, system_message: str, user_prompt: str) -> str:
        endpoint = f"{self.base_url}/api/chat"

        payload = {
            "model": self.actual_model_tag,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "options": self.options
        }

        try:
            response = requests.post(endpoint, json=payload, timeout=300)  # Longer timeout for local inference
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]
        except requests.exceptions.ConnectionError:
            raise LLMError(f"Could not connect to Ollama at {self.base_url}. Ensure it is running on the A800 node.")
        except KeyError:
            raise LLMError(f"Unexpected Ollama response: {response.text}")

class LLMFactory:

    @staticmethod
    def create_client(provider: str, config_path: str = "configs/settings.yaml", **kwargs) -> BaseLLMClient:

        with open(config_path, 'r') as f:
            full_config = yaml.safe_load(f)

        llm_config = full_config.get("llm", {})
        api_providers = llm_config.get("api_providers", {})
        local_providers = llm_config.get("local_providers", {})

        if provider == "google":
            conf = api_providers.get("google")
            return GoogleGenAIClient(conf, conf["api_key_env"])

        elif provider == "openai":
            conf = api_providers.get("openai")
            return OpenAICompatibleClient(conf, conf["api_key_env"])

        elif provider == "deepseek":
            conf = api_providers.get("deepseek")
            return OpenAICompatibleClient(conf, conf["api_key_env"])

        ollama_conf = local_providers.get("ollama", {})
        ollama_models = ollama_conf.get("models", {})

        if provider in ollama_models:
            return OllamaClient(ollama_conf, model_alias=provider)

        if provider == "ollama":

            raise ValueError("For local models, please specify the alias (e.g., 'qwen_32b') not just 'ollama'.")

        raise ValueError(f"Unknown LLM provider: {provider}")