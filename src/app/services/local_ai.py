"""LocalAI service for testing without API keys."""

import httpx
from typing import Optional


class LocalAI:
    """LocalAI client that mimics OpenAI's API interface."""

    HTTP_OK = 200
    HTTP_200_OK = 200

    def __init__(self, base_url: str = "http://localhost:8080/v1"):
        """Initialize LocalAI client.

        Args:
            base_url: LocalAI server URL
        """
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
        self.model = "gpt4all-j"  # Default small model

    @classmethod
    async def setup(cls) -> "LocalAI":
        """Setup LocalAI server with a small model for testing."""
        client = cls()
        await client._ensure_model()
        return client

    async def _ensure_model(self):
        """Ensure model is downloaded and loaded."""
        try:
            # Check if model is loaded
            async with self.client as client:
                response = await client.get("/models")
                if response.status_code == self.HTTP_200_OK:
                    models = response.json()
                    if any(m["id"] == self.model for m in models):
                        return True

            # Load model if not present
            async with self.client as client:
                response = await client.post(
                    "/models/apply",
                    json={"id": self.model, "url": "https://gpt4all.io/models/ggml-gpt4all-j.bin"},
                )
                return response.status_code == self.HTTP_200_OK

        except httpx.RequestError:
            raise RuntimeError(
                "LocalAI server not running. Please start it with: "
                "docker run -p 8080:8080 localai/localai:latest"
            )

    async def generate(self, prompt: str, context: Optional[str] = None, **kwargs) -> str:
        """Generate completion using LocalAI."""
        messages = []
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": prompt})

        try:
            async with self.client as client:
                response = await client.post(
                    "/chat/completions",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": kwargs.get("temperature", 0.7),
                        "max_tokens": kwargs.get("max_tokens", 500),
                    },
                )

                if response.status_code == self.HTTP_200_OK:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    raise RuntimeError(f"LocalAI error: {response.text}")

        except httpx.RequestError as e:
            raise RuntimeError(f"LocalAI request failed: {e!s}")

    async def close(self):
        """Close client connection."""
        await self.client.aclose()
