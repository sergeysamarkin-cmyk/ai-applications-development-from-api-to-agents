import json
import logging
from collections import defaultdict
from typing import AsyncGenerator

from openai import AsyncOpenAI

from t13_final_task.task.agent.models import Message
from t13_final_task.task.agent.models import Role
from t13_final_task.task.agent.guardrail import UMSDataGuardrail
from t13_final_task.task.agent.tools.base import BaseTool

logger = logging.getLogger(__name__)


def _sse(payload: dict) -> str:
    """Format a dict as one Server-Sent Events message"""
    return f"data: {json.dumps(payload)}\n\n"


class UMSAgent:
    """Handles AI model interactions and integrates with MCP client"""

    def __init__(
            self,
            api_key: str,
            model: str,
            tools: list[BaseTool]
    ):
        self.tools: dict[str, BaseTool] = {tool.name: tool for tool in tools}
        self.tools_schemas = [tool.schema for tool in tools]
        self.model = model
        self.async_openai = AsyncOpenAI(api_key=api_key)
        self.guardrail = UMSDataGuardrail()

    async def response(self, messages: list[Message]) -> Message:
        """Non-streaming completion with tool calling support"""
        request_data = {
            "model": self.model,
            "messages": [msg.to_dict() for msg in messages],
            "tools": self.tools_schemas,
            "stream": False,
            # GPT-5.6 supports function tools in Chat Completions only without reasoning
            "reasoning_effort": "none",
        }
        response = await self.async_openai.chat.completions.create(**request_data)
        response_message = response.choices[0].message

        ai_message = Message(role=Role.ASSISTANT, content=response_message.content or "")
        if response_message.tool_calls:
            ai_message.tool_calls = [tool_call.model_dump() for tool_call in response_message.tool_calls]

        if ai_message.tool_calls:
            messages.append(ai_message)
            await self._call_tools(ai_message, messages)
            return await self.response(messages)

        return ai_message

    async def stream_response(self, messages: list[Message]) -> AsyncGenerator[str, None]:
        """
        Streaming completion with tool calling support.
        Yields SSE-formatted chunks.
        """
        request_data = {
            "model": self.model,
            "messages": [msg.to_dict() for msg in messages],
            "tools": self.tools_schemas,
            "stream": True,
            "reasoning_effort": "none",
        }
        stream = await self.async_openai.chat.completions.create(**request_data)

        content_buffer = ""
        tool_deltas = []

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if delta.content:
                content_buffer += delta.content
                yield _sse({"choices": [{"index": 0, "delta": {"content": delta.content}, "finish_reason": None}]})

            if delta.tool_calls:
                tool_deltas.extend(delta.tool_calls)

        if tool_deltas:
            tool_calls = self._collect_tool_calls(tool_deltas)
            ai_message = Message(role=Role.ASSISTANT, content=content_buffer, tool_calls=tool_calls)
            messages.append(ai_message)

            # Tell the frontend which tools are being called
            for tool_call in tool_calls:
                try:
                    arguments = json.loads(tool_call["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                yield _sse({"tool_activity": {
                    "type": "call",
                    "name": tool_call["function"]["name"],
                    "arguments": arguments,
                }})

            await self._call_tools(ai_message, messages, silent=True)

            # Tell the frontend about the results (already filtered by the guardrail)
            for tool_call, tool_message in zip(tool_calls, messages[-len(tool_calls):]):
                yield _sse({"tool_activity": {
                    "type": "result",
                    "name": tool_call["function"]["name"],
                    "content": tool_message.content,
                }})

            async for chunk in self.stream_response(messages):
                yield chunk
            return

        messages.append(Message(role=Role.ASSISTANT, content=content_buffer))
        yield _sse({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
        yield "data: [DONE]\n\n"

    def _collect_tool_calls(self, tool_deltas):
        """Convert streaming tool call deltas to complete tool calls"""
        tool_dict = defaultdict(lambda: {"id": None, "function": {"arguments": "", "name": None}, "type": None})

        for delta in tool_deltas:
            idx = delta.index
            if delta.id:
                tool_dict[idx]["id"] = delta.id
            if delta.function and delta.function.name:
                tool_dict[idx]["function"]["name"] = delta.function.name
            if delta.function and delta.function.arguments:
                tool_dict[idx]["function"]["arguments"] += delta.function.arguments
            if delta.type:
                tool_dict[idx]["type"] = delta.type

        return list(tool_dict.values())

    async def _call_tools(self, ai_message: Message, messages: list[Message], silent: bool = False):
        """Execute tool calls using MCP client"""
        for tool_call in ai_message.tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_call_id = tool_call["id"]
            tool = self.tools.get(tool_name)

            if tool is None:
                messages.append(Message(
                    role=Role.TOOL,
                    tool_call_id=tool_call_id,
                    content=f"ERROR: tool '{tool_name}' not found",
                ))
                continue

            try:
                arguments = json.loads(tool_call["function"]["arguments"] or "{}")
            except json.JSONDecodeError as e:
                messages.append(Message(
                    role=Role.TOOL,
                    tool_call_id=tool_call_id,
                    content=f"ERROR: invalid JSON arguments: {e}",
                ))
                continue

            if not silent:
                logger.info("Calling tool %s with %s", tool_name, arguments)

            tool_message = await tool.execute(tool_call_id, arguments)

            # PII filtering: credit card and salary data never reach the model or the stored conversation
            tool_message.content = self.guardrail.redact(str(tool_message.content))
            messages.append(tool_message)
