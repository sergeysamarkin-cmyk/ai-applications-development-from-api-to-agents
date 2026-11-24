import json
import aiohttp
import requests

from commons.models.message import Message
from commons.models.role import Role
from t1_llm_api.base_client import AIClient


class CustomGeminiAIClient(AIClient):
    """
    Custom HTTP client for Google Gemini API.

    This implementation uses raw HTTP requests (requests/aiohttp) instead of
    the official SDK, demonstrating how to interact with Gemini's API directly
    and handle its Server-Sent Events (SSE) streaming format.
    """

    def _headers(self) -> dict:
        return {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }

    def _request_data(self, messages: list[Message], **kwargs) -> dict:
        data = {
            "system_instruction": {"parts": [{"text": self._system_prompt}]},
            # Gemini roles are only "user" and "model"
            "contents": [
                {
                    "role": "model" if m.role == Role.ASSISTANT else "user",
                    "parts": [{"text": m.content}],
                }
                for m in messages
            ],
        }
        if "max_tokens" in kwargs:
            data["generationConfig"] = {"maxOutputTokens": kwargs["max_tokens"]}
        return data

    @staticmethod
    def _extract_text(candidates: list[dict]) -> str:
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))

    def response(self, messages: list[Message], **kwargs) -> Message:
        """
        Get a synchronous response using raw HTTP POST request.

        Args:
            messages (list[Message]): The conversation history.
            **kwargs: Additional parameters like max_tokens (default: 1024).

        Returns:
            Message: The AI's response message.

        Raises:
            ValueError: If the API response contains no candidates.
            Exception: If the HTTP request fails (non-200 status code).

        Note:
            The URL is constructed by appending ':generateContent' to the model endpoint.
            Uses 'x-goog-api-key' header for authentication.
            Response candidates contain content parts that are concatenated.
        """
        url = f"{self._endpoint}/{self._model_name}:generateContent"

        resp = requests.post(url, headers=self._headers(), json=self._request_data(messages, **kwargs))
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}: {resp.text}")

        candidates = resp.json().get("candidates")
        if not candidates:
            raise ValueError("No candidates in response found")

        content = self._extract_text(candidates)
        print(content)
        return Message(Role.ASSISTANT, content)

    async def stream_response(self, messages: list[Message], **kwargs) -> Message:
        """
        Get a streaming response using raw HTTP with Server-Sent Events (SSE).

        The response is streamed using Gemini's SSE format, with text chunks
        printed immediately as they arrive.

        Args:
            messages (list[Message]): The conversation history.
            **kwargs: Additional parameters like max_tokens (default: 1024).

        Returns:
            Message: The complete AI response message after all chunks are received.

        Note:
            The URL is constructed with ':streamGenerateContent?alt=sse' endpoint.
            Uses Server-Sent Events (SSE) format where each line starts with "data: ".
            Each SSE chunk contains candidates with content parts.
            Each text chunk is printed to stdout as it arrives.
        """
        url = f"{self._endpoint}/{self._model_name}:streamGenerateContent?alt=sse"

        contents = []
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self._headers(), json=self._request_data(messages, **kwargs)) as resp:
                if resp.status != 200:
                    raise Exception(f"HTTP {resp.status}: {await resp.text()}")

                async for raw_line in resp.content:
                    line = raw_line.decode("utf-8").strip()
                    if not line.startswith("data: "):
                        continue
                    chunk = json.loads(line[len("data: "):])
                    candidates = chunk.get("candidates")
                    if candidates:
                        text = self._extract_text(candidates)
                        if text:
                            print(text, end="", flush=True)
                            contents.append(text)
        print()
        return Message(Role.ASSISTANT, "".join(contents))