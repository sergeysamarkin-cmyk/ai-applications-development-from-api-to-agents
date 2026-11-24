import json
import aiohttp
import requests

from commons.models.message import Message
from commons.models.role import Role
from t1_llm_api.openai.base import BaseOpenAIClient


class CustomOpenAIClient(BaseOpenAIClient):
    """
    Custom HTTP client for OpenAI Chat Completions API.

    This implementation uses raw HTTP requests (requests/aiohttp) instead of
    the official SDK, providing more control over the HTTP layer and demonstrating
    how to interact with the API directly.
    """

    def _prepare_messages(self, messages: list[Message]) -> list[dict]:
        history = [Message(Role.SYSTEM, self._system_prompt)] + list(messages)
        return [m.to_dict() for m in history]

    def response(self, messages: list[Message], **kwargs) -> Message:
        """
        Get a synchronous response using raw HTTP POST request.

        Args:
            messages (list[Message]): The conversation history.
            **kwargs: Additional parameters for the API (currently unused).

        Returns:
            Message: The AI's response message.

        Raises:
            ValueError: If the API response contains no choices.
            Exception: If the HTTP request fails (non-200 status code).

        Note:
            The system prompt is automatically prepended to the messages.
            The response is printed to stdout before being returned.
        """
        headers = {
            "Authorization": self._api_key,
            "Content-Type": "application/json",
        }
        request_data = {
            "model": self._model_name,
            "messages": self._prepare_messages(messages),
        }

        resp = requests.post(self._endpoint, headers=headers, json=request_data)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}: {resp.text}")

        choices = resp.json().get("choices")
        if not choices:
            raise ValueError("No choices in response found")

        content = choices[0]["message"].get("content") or ""
        print(content)
        return Message(Role.ASSISTANT, content)

    async def stream_response(self, messages: list[Message], **kwargs) -> Message:
        """
        Get a streaming response using raw HTTP with Server-Sent Events (SSE).

        The response is streamed token-by-token using OpenAI's SSE format,
        with each chunk printed immediately as it arrives.

        Args:
            messages (list[Message]): The conversation history.
            **kwargs: Additional parameters for the API (currently unused).

        Returns:
            Message: The complete AI response message after all chunks are received.

        Note:
            The system prompt is automatically prepended to the messages.
            Each token is printed to stdout as it arrives.
            Uses Server-Sent Events (SSE) format where each line starts with "data: ".
        """
        headers = {
            "Authorization": self._api_key,
            "Content-Type": "application/json",
        }
        request_data = {
            "model": self._model_name,
            "messages": self._prepare_messages(messages),
            "stream": True,
        }

        contents = []
        async with aiohttp.ClientSession() as session:
            async with session.post(self._endpoint, headers=headers, json=request_data) as resp:
                if resp.status != 200:
                    raise Exception(f"HTTP {resp.status}: {await resp.text()}")

                async for raw_line in resp.content:
                    line = raw_line.decode("utf-8").strip()
                    if not line.startswith("data: "):
                        continue
                    data = line[len("data: "):]
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    choices = chunk.get("choices")
                    if choices:
                        delta = choices[0].get("delta", {}).get("content")
                        if delta:
                            print(delta, end="", flush=True)
                            contents.append(delta)
        print()
        return Message(Role.ASSISTANT, "".join(contents))
