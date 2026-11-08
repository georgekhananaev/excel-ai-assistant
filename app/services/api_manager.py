"""
API Manager for the Excel AI Assistant.
Handles interactions with both OpenAI API and local Ollama API.
"""

import logging
import time
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple

from openai import OpenAI, APIError, RateLimitError

from app.services.ollama_api_manager import OllamaAPIManager


class APIType(Enum):
    """Enum for API types"""
    OPENAI = "openai"
    OLLAMA = "ollama"


class APIManager:
    """Manager for interacting with AI APIs (OpenAI and Ollama)"""

    def __init__(self, api_key: str = "", model: str = "",
                 api_type: str = "openai", ollama_url: str = "http://localhost:11434",
                 openai_base_url: str = "", max_requests_per_minute: int = 20):
        """Initialize the API manager.

        openai_base_url: leave empty for the official OpenAI API, or point it at any
        OpenAI-compatible server (for example http://localhost:1234/v1 for LM Studio).
        max_requests_per_minute: 0 disables rate limiting.
        """
        self.api_key = api_key
        self.model = model
        self.api_type = APIType(api_type)
        self.client = None
        self.logger = logging.getLogger("APIManager")
        self.openai_base_url = openai_base_url

        # Initialize Ollama manager
        self.ollama_url = ollama_url
        self.ollama_manager = OllamaAPIManager(base_url=ollama_url)

        # Rate limiting
        self.request_count = 0
        self.request_start_time = time.time()
        self.max_requests_per_minute = max_requests_per_minute

        # Initialize if API key is provided for OpenAI
        if api_key and self.api_type == APIType.OPENAI:
            self.initialize()

    def initialize(self, api_key: Optional[str] = None) -> bool:
        """Initialize the API client"""
        if self.api_type == APIType.OPENAI:
            if api_key:
                self.api_key = api_key
            if not self.api_key:
                self.logger.error("API Key is required for OpenAI")
                return False
            try:
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.openai_base_url or None
                )
                return True
            except Exception as e:
                self.logger.error(f"Failed to initialize OpenAI client: {e}")
                return False
        else:  # OLLAMA
            # No initialization needed for Ollama as it's handled by requests
            return True

    def set_api_type(self, api_type: str) -> None:
        """Set the API type (openai or ollama)"""
        self.api_type = APIType(api_type)

    def set_model(self, model: str) -> None:
        """Set the model to use for API calls"""
        self.model = model
        if self.api_type == APIType.OLLAMA:
            self.ollama_manager.set_model(model)

    def set_ollama_url(self, url: str) -> None:
        """Set the Ollama API URL"""
        self.ollama_url = url
        self.ollama_manager.set_base_url(url)

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models based on current API type"""
        if self.api_type == APIType.OPENAI:
            try:
                models = self.client.models.list()
                return [{"id": m.id, "name": m.id, "api": "openai"} for m in models.data]
            except Exception as e:
                self.logger.error(f"Error getting models: {e}")
                return []
        else:  # OLLAMA
            # Fetch models from Ollama
            success, models, error = self.ollama_manager.list_available_models()
            if success and models:
                return [{"id": model, "name": model, "api": "ollama"} for model in models]
            else:
                # Return empty list if error
                self.logger.error(f"Error getting Ollama models: {error}")
                return []

    def test_connection(self) -> Tuple[bool, str]:
        """Test the API connection"""
        if self.api_type == APIType.OPENAI:
            if not self.client:
                if not self.initialize():
                    return False, "API client not initialized"

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Test connection"}
                    ],
                    max_tokens=5  # Minimal tokens for quick test
                )

                # Check if response is valid
                if hasattr(response, 'choices') and len(response.choices) > 0:
                    return True, "Connection successful"
                else:
                    return False, "Invalid response from API"

            except RateLimitError as e:
                return False, f"Rate limit exceeded: {str(e)}"
            except APIError as e:
                return False, f"API Error: {str(e)}"
            except Exception as e:
                return False, f"Error: {str(e)}"
        else:  # OLLAMA
            # Use Ollama manager to test connection
            return self.ollama_manager.test_connection()

    def process_single_cell(
            self,
            cell_content: str,
            system_prompt: str,
            user_prompt: str,
            temperature: float = 0.3,
            max_tokens: int = 150,
            context_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Process a single cell using the selected API

        Args:
            cell_content: The content of the cell being processed
            system_prompt: System prompt for the AI
            user_prompt: User prompt for the AI
            temperature: Temperature parameter for generation
            max_tokens: Maximum tokens in response
            context_data: Optional dictionary with context data from other columns

        Returns:
            Tuple of (success, result, error_message)
        """
        if self.api_type == APIType.OPENAI:
            return self._process_openai(cell_content, system_prompt, user_prompt, temperature, max_tokens, context_data)
        else:  # OLLAMA
            return self.ollama_manager.process_single_cell(
                cell_content, system_prompt, user_prompt, temperature, max_tokens, context_data
            )

    def _process_openai(
            self,
            cell_content: str,
            system_prompt: str,
            user_prompt: str,
            temperature: float = 0.3,
            max_tokens: int = 150,
            context_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Process a single cell using OpenAI API"""
        if not self.client:
            if not self.initialize():
                return False, None, "API client not initialized"

        # Wait if we're at the rate limit
        self._check_rate_limit()

        formatted_prompt = f"{user_prompt}\n\nCell content: {cell_content}"
        
        # Add context information if available
        if context_data and len(context_data) > 0:
            context_text = "\n\nContext information:\n"
            for key, value in context_data.items():
                context_text += f"- {key}: {value}\n"
            formatted_prompt += context_text

        try:
            # Make API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": formatted_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )

            # Increment request counter
            self._increment_request_count()

            # Extract result text
            result = response.choices[0].message.content.strip()
            return True, result, None

        except RateLimitError as e:
            return False, None, f"Rate limit exceeded: {str(e)}"
        except APIError as e:
            return False, None, f"API Error: {str(e)}"
        except Exception as e:
            self.logger.error(f"API Error: {str(e)}")
            return False, None, f"Error: {str(e)}"

    def _increment_request_count(self) -> None:
        """Track API request count for rate limiting"""
        current_time = time.time()
        # Reset counter if a minute has passed
        if current_time - self.request_start_time > 60:
            self.request_count = 0
            self.request_start_time = current_time

        self.request_count += 1

    def _check_rate_limit(self) -> bool:
        """Wait until another request fits in the per-minute limit.

        Runs in a worker thread, so sleeping here only pauses the batch, not the UI.
        """
        if not self.max_requests_per_minute:
            return True
        current_time = time.time()
        elapsed = current_time - self.request_start_time
        if elapsed > 60:
            self.request_count = 0
            self.request_start_time = current_time
        elif self.request_count >= self.max_requests_per_minute:
            wait = 60 - elapsed
            self.logger.info(f"Rate limit of {self.max_requests_per_minute}/min reached, waiting {wait:.0f}s")
            time.sleep(wait)
            self.request_count = 0
            self.request_start_time = time.time()
        return True
