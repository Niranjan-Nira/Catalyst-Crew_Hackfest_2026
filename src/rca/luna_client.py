import os
from typing import Optional

from ..config import LUNA_API_KEY, LUNA_BASE_URL, LUNA_ENABLED, LUNA_MODEL

class LunaClient:
    """
    Client connector for the Luna 5.6 model (hack-fest-gpt-5.6-luna).
    Implements Azure AI Inference ChatCompletionsClient from test.py
    with seamless local deterministic fallback if network/VPN is unreachable.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        raw_key = api_key or os.getenv("LUNA_API_KEY", LUNA_API_KEY)
        self.api_key = raw_key.strip()
        self.base_url = base_url or os.getenv("LUNA_BASE_URL", LUNA_BASE_URL).rstrip("/")
        self.model = os.getenv("LUNA_MODEL", LUNA_MODEL)
        self.last_error: Optional[str] = None
        self.is_configured = bool(
            LUNA_ENABLED
            and self.api_key
            and "YOUR_API_KEY" not in self.api_key
            and len(self.api_key) > 5
        )

    def generate_rca_reasoning(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """
        Sends grounded anomaly evidence and RAG context to Luna 5.6 for reasoning.
        """
        if not self.is_configured:
            self.last_error = "Luna is disabled or its API key is not configured."
            return None

        # 1. Attempt Azure AI Inference client (test.py implementation)
        try:
            from azure.ai.inference import ChatCompletionsClient
            from azure.core.credentials import AzureKeyCredential
            from azure.ai.inference.models import SystemMessage, UserMessage

            client = ChatCompletionsClient(
                endpoint=self.base_url,
                credential=AzureKeyCredential(self.api_key),
                api_version="2025-03-01-preview"
            )

            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(UserMessage(content=prompt))

            response = client.complete(
                messages=messages,
                model=self.model,
                headers={"Authorization": self.api_key},
                connection_timeout=10,
                read_timeout=30
            )
            if response and response.choices:
                return response.choices[0].message.content
        except Exception as exc:
            self.last_error = f"Azure client: {type(exc).__name__}: {exc}"

        # 2. Attempt direct REST call fallback
        try:
            import requests
            url = f"{self.base_url}/chat/completions"
            headers = {"Authorization": self.api_key, "Content-Type": "application/json"}
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt or (
                            "You are an expert Endpoint Diagnostics and Root Cause Analysis agent. "
                            "You analyze Windows diagnostic logs and correlate evidence. "
                            "Do not guess. Only state root causes directly supported by the evidence chain."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            self.last_error = f"REST API: HTTP {resp.status_code}"
        except Exception as exc:
            self.last_error = f"REST API: {type(exc).__name__}: {exc}"

        return None
