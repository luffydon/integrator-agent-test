import os
import json
from typing import Dict, List
from openai import AsyncOpenAI

# Read OpenRouter configuration from environment variables
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL")
OPENROUTER_SITE_NAME = os.getenv("OPENROUTER_SITE_NAME")
LLM_MODEL = os.getenv("LLM_MODEL")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

class LLMClient:
    def __init__(self):
        if not OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY is not set in the .env file.")
        
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )

    async def get_agent_response(self, messages: List[Dict], tools: List[Dict]) -> Dict:
        """
        Gets a response from the LLM, potentially including a tool call.
        """
        try:
            completion = await self.client.chat.completions.create(
                model=LLM_MODEL,
                temperature=LLM_TEMPERATURE,
                extra_headers={
                    "HTTP-Referer": OPENROUTER_SITE_URL,
                    "X-Title": OPENROUTER_SITE_NAME,
                },
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            return completion.choices[0].message
            
        except Exception as e:
            print(f"❌ LLM request failed: {e}")
            # Return a valid message object on failure
            return {"role": "assistant", "content": "I'm sorry, I encountered an error."}