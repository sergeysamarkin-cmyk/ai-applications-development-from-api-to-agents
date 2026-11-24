import json
import aiohttp
import requests

from commons.models.message import Message
from commons.models.role import Role
from t1_llm_api.openai.base import BaseOpenAIClient


class CustomOpenAIResponsesClient(BaseOpenAIClient):
    """
    Custom HTTP client for OpenAI Responses API.

    This implementation uses raw HTTP requests (requests/aiohttp) instead of
    the official SDK, demonstrating how to interact with the Responses API directly
    and handle its unique event-based streaming format.
    """

    @staticmethod
    def _prepare_input(messages: list[Message]) -> list[dict]:
        return [{"role": m.role.value, "content": m.content} for m in messages]

    def response(self, messages: list[Message], **kwargs) -> Message:
        """
        Get a synchronous response using raw HTTP POST request.

        Args:
            messages (list[Message]): The conversation history.
            **kwargs: Additional parameters for the API (currently unused).

        Returns:
            Message: The AI's response message.

        Raises:
            ValueError: If the API response contains no output text.
            Exception: If the HTTP request fails (non-200 status code).

        Note:
            Uses the Responses API format with 'instructions' and 'input' parameters.
            The response is printed to stdout before being returned.
        """
        headers = {
            "Authorization": self._api_key,
            "Content-Type": "application/json",
        }
        request_data = {
            "model": self._model_name,
            "instructions": self._system_prompt,
            "input": self._prepare_input(messages),
        }

        resp = requests.post(self._endpoint, headers=headers, json=request_data)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}: {resp.text}")

        texts = []
        for item in resp.json().get("output", []):
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        texts.append(part.get("text", ""))
        if not texts:
            raise ValueError("No output text in response found")

        content = "".join(texts)
        print(content)
        return Message(Role.ASSISTANT, content)

    async def stream_response(self, messages: list[Message], **kwargs) -> Message:
        """
        Get a streaming response using raw HTTP with event-based streaming.

        The Responses API uses a different SSE format than Chat Completions,
        with explicit event types and data fields.

        Args:
            messages (list[Message]): The conversation history.
            **kwargs: Additional parameters for the API (currently unused).

        Returns:
            Message: The complete AI response message after all deltas are received.

        Note:
            Uses event-based Server-Sent Events (SSE) format.
            Listens for 'response.output_text.delta' events to build the response.
            Each line with "event: " specifies the event type, followed by "data: " with the payload.
        """
        headers = {
            "Authorization": self._api_key,
            "Content-Type": "application/json",
        }
        request_data = {
            "model": self._model_name,
            "instructions": self._system_prompt,
            "input": self._prepare_input(messages),
            "stream": True,
        }

        contents = []
        async with aiohttp.ClientSession() as session:
            async with session.post(self._endpoint, headers=headers, json=request_data) as resp:
                if resp.status != 200:
                    raise Exception(f"HTTP {resp.status}: {await resp.text()}")

                event_type = None
                async for raw_line in resp.content:
                    line = raw_line.decode("utf-8").strip()
                    if line.startswith("event: "):
                        event_type = line[len("event: "):]
                    elif line.startswith("data: "):
                        payload = json.loads(line[len("data: "):])
                        # Errors can arrive inside a 200 stream, so check them explicitly
                        if event_type in ("error", "response.failed"):
                            raise Exception(f"Stream error: {payload}")
                        if event_type == "response.output_text.delta":
                            delta = payload.get("delta", "")
                            if delta:
                                print(delta, end="", flush=True)
                                contents.append(delta)
        print()
        return Message(Role.ASSISTANT, "".join(contents))
