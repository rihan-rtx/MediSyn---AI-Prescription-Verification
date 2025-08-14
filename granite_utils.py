
"""
Utility for querying IBM Granite models via Hugging Face Inference API with caching
"""

import os
import aiohttp
import logging
from typing import Dict, Any, Optional
from collections import OrderedDict

logger = logging.getLogger(__name__)

# In-memory cache with max size
class LRUCache:
    def __init__(self, capacity: int = 100):
        self.cache = OrderedDict()
        self.capacity = capacity
    
    def get(self, key: str) -> Optional[str]:
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None
    
    def put(self, key: str, value: str):
        self.cache[key] = value
        self.cache.move_to_end(key)
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

# Global cache instance
response_cache = LRUCache(capacity=100)

async def query_granite(prompt: str, parameters: Optional[Dict[str, Any]] = None, cache_key: Optional[str] = None) -> str:
    """
    Query the Granite model asynchronously via HF Inference API with caching.
    
    Args:
        prompt: The input prompt for the model.
        parameters: Optional dict for generation params (e.g., max_new_tokens).
        cache_key: Optional key for caching the response.
        
    Returns:
        Generated text from the model.
        
    Raises:
        Exception on API failure.
    """
    # Check cache first
    if cache_key:
        cached_response = response_cache.get(cache_key)
        if cached_response:
            logger.info(f"Cache hit for key: {cache_key}")
            return cached_response
    
    model_name = os.environ.get('GRANITE_MODEL_NAME', 'ibm-granite/granite-3b-code-instruct')
    api_token = os.environ.get('HUGGINGFACE_API_TOKEN')
    if not api_token:
        raise ValueError("HUGGINGFACE_API_TOKEN not set in .env")
    
    url = f"https://api-inference.huggingface.co/models/{model_name}"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    
    data = {
        "inputs": prompt,
        "parameters": parameters or {
            "max_new_tokens": 256,
            "temperature": 0.7,
            "top_p": 0.95,
            "do_sample": True,
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    if isinstance(result, list) and result:
                        response_text = result[0].get('generated_text', '').strip()
                        if cache_key:
                            response_cache.put(cache_key, response_text)
                            logger.info(f"Cached response for key: {cache_key}")
                        return response_text
                    return ''
                else:
                    error_text = await response.text()
                    logger.error(f"HF API error: {response.status} - {error_text}")
                    raise Exception(f"HF API failed: {error_text}")
    except Exception as e:
        logger.error(f"Error querying Granite: {str(e)}")
        raise
