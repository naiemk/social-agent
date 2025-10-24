"""
Model adapters for different LLM providers.

This module provides a unified interface for working with different LLM providers
through the ADK framework. It supports both Google Gemini and OpenAI models.
"""

import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from google.adk.agents import LlmAgent
from google.genai import types
import openai

from config import settings


class ModelAdapter(ABC):
    """Abstract base class for model adapters."""
    
    def __init__(self, model_name: str, api_key: str):
        self.model_name = model_name
        self.api_key = api_key
        self._setup_client()
    
    @abstractmethod
    def _setup_client(self) -> None:
        """Set up the client for the specific model provider."""
        pass
    
    @abstractmethod
    def create_agent(self, name: str, description: str, instruction: str, output_key: str = "result") -> LlmAgent:
        """Create an LLM agent using this model."""
        pass
    
    @abstractmethod
    def validate_connection(self) -> bool:
        """Validate that the connection to the model works."""
        pass


class GeminiAdapter(ModelAdapter):
    """Adapter for Google Gemini models."""
    
    def _setup_client(self) -> None:
        """Set up the Gemini client."""
        os.environ["GOOGLE_API_KEY"] = self.api_key
    
    def create_agent(self, name: str, description: str, instruction: str, output_key: str = "result") -> LlmAgent:
        """Create a Gemini LLM agent."""
        return LlmAgent(
            model=self.model_name,
            name=name,
            description=description,
            instruction=instruction,
            output_key=output_key,
        )
    
    def validate_connection(self) -> bool:
        """Validate Gemini connection."""
        try:
            # Simple test to validate the connection
            from google.genai import GenerativeModel
            model = GenerativeModel(self.model_name)
            response = model.generate_content("Hello")
            return response.text is not None
        except Exception:
            return False


class OpenAIAdapter(ModelAdapter):
    """Adapter for OpenAI models."""
    
    def _setup_client(self) -> None:
        """Set up the OpenAI client."""
        openai.api_key = self.api_key
    
    def create_agent(self, name: str, description: str, instruction: str, output_key: str = "result") -> LlmAgent:
        """Create an OpenAI LLM agent."""
        # Note: ADK might not directly support OpenAI models, so we'll use a custom approach
        # This is a placeholder implementation that would need to be adapted based on ADK's capabilities
        return LlmAgent(
            model=self.model_name,
            name=name,
            description=description,
            instruction=instruction,
            output_key=output_key,
        )
    
    def validate_connection(self) -> bool:
        """Validate OpenAI connection."""
        try:
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            return response.choices[0].message.content is not None
        except Exception:
            return False


def create_adapter(model_name: str = None, api_key: str = None) -> ModelAdapter:
    """
    Create a model adapter based on the model name.
    
    Args:
        model_name: The model name (defaults to settings.model_name)
        api_key: The API key (defaults to appropriate key from settings)
    
    Returns:
        A configured model adapter
    """
    model_name = model_name or settings.model_name
    api_key = api_key or _get_api_key_for_model(model_name)
    
    if model_name.startswith('gemini'):
        return GeminiAdapter(model_name, api_key)
    elif model_name.startswith('gpt'):
        return OpenAIAdapter(model_name, api_key)
    else:
        raise ValueError(f"Unknown model type: {model_name}")


def _get_api_key_for_model(model_name: str) -> str:
    """Get the appropriate API key for the given model."""
    if model_name.startswith('gemini'):
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required for Gemini models")
        return settings.google_api_key
    elif model_name.startswith('gpt'):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI models")
        return settings.openai_api_key
    else:
        raise ValueError(f"Unknown model type: {model_name}")
