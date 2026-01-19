import logging
import math
from typing import List, Dict, Optional, Tuple
import tiktoken

logger = logging.getLogger(__name__)

class TokenManager:
    """Manages token counting and ensures prompts fit within LLM context windows."""

    # MODEL_LIMITS = {
    #     "gpt-3.5-turbo": 16000,
    #     "gemini-2.0-flash": 30000,
    #     "deepseek-chat": 32000,
    #     "qwen2.5-coder:7b": 32000,
    #     "qwen2.5-coder:32b": 32000,
    #     "llama3:8b": 8000,
    # }

    MODEL_LIMITS = {
        "gpt-3.5-turbo": 10000,
        "gemini-2.0-flash": 10000,
        "deepseek-chat": 12000,
        "qwen2.5-coder:7b": 12000,
        "qwen2.5-coder:32b": 12000,
        "llama3:8b": 8000,
    }
    OUTPUT_RESERVE = 1024

    def __init__(self, model_name: str):

        self.model_name = model_name
        self.max_context_length = self._get_model_limit(model_name)

        try:
            self.encoder = tiktoken.encoding_for_model(model_name)
        except KeyError:
            logger.debug(f"No specific tokenizer found for {model_name}. Using cl100k_base proxy.")
            self.encoder = tiktoken.get_encoding("cl100k_base")

    def _get_model_limit(self, model_name: str) -> int:
        for key, limit in self.MODEL_LIMITS.items():
            if key in model_name.lower():
                return limit
        return 4096

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(self.encoder.encode(text))

    def check_fit(self, full_prompt: str) -> bool:
        count = self.count_tokens(full_prompt)
        limit = self.max_context_length - self.OUTPUT_RESERVE
        if count > limit:
            logger.warning(f"Prompt size {count} exceeds safe limit {limit} for {self.model_name}.")
            return False
        return True

    def optimize_prompt(self,
                        static_parts: List[str],
                        dynamic_context: str,
                        feedback_part: str = "") -> str:

        static_text = "\n".join(static_parts)
        feedback_tokens = self.count_tokens(feedback_part)
        static_tokens = self.count_tokens(static_text)

        safe_limit = self.max_context_length - self.OUTPUT_RESERVE
        available_for_context = safe_limit - static_tokens - feedback_tokens

        if available_for_context < 0:
            logger.warning("Static parts exceed context limit! Attempting to truncate feedback.")
            feedback_budget = max(0, safe_limit - static_tokens)
            feedback_part = self._truncate_text(feedback_part, feedback_budget, from_end=True)  # Keep error end

            feedback_tokens = self.count_tokens(feedback_part)
            available_for_context = safe_limit - static_tokens - feedback_tokens

            if available_for_context < 0:
                logger.error("Critical: Even without context and feedback, prompt is too long.")
                return static_text

        current_context_tokens = self.count_tokens(dynamic_context)

        final_context = dynamic_context
        if current_context_tokens > available_for_context:
            logger.info(f"Truncating context from {current_context_tokens} to {available_for_context} tokens.")
            final_context = self._truncate_text(dynamic_context, available_for_context)
            final_context += "\n... (Context truncated due to length) ..."

        return final_context

    def _truncate_text(self, text: str, max_tokens: int, from_end: bool = False) -> str:

        if max_tokens <= 0:
            return ""

        tokens = self.encoder.encode(text)
        if len(tokens) <= max_tokens:
            return text

        if from_end:
            truncated_tokens = tokens[-max_tokens:]
        else:
            truncated_tokens = tokens[:max_tokens]

        return self.encoder.decode(truncated_tokens)