import json

from openai import OpenAI

from commons.models.message import Message
from commons.models.role import Role
from t12_skills.custom.tools.base import BaseTool


class T12Agent:

    def __init__(self, client: OpenAI, model: str, tools: list[BaseTool] | None = None):
        self._client = client
        self._model = model
        self._tools: dict[str, BaseTool] = {tool.name: tool for tool in tools}
        self._tools_schemas = [tool.schema for tool in tools] if tools else []
        print(json.dumps(self._tools_schemas, indent=4))

    async def chat_completion(self, messages: list[Message], log_messages: bool = False) -> Message:
        if log_messages:
            print("\n--- REQUEST ---")
            print(json.dumps([msg.to_dict() for msg in messages], indent=2, default=str))

        return await self._chat_completion(messages, log_messages)

    async def _chat_completion(self, messages: list[Message], log_messages: bool = False) -> Message:
        request = {
            "model": self._model,
            "messages": [msg.to_dict() for msg in messages],
            "tools": self._tools_schemas,
            # GPT-5.6 supports function tools in Chat Completions only without reasoning
            "reasoning_effort": "none",
        }
        choice = self._client.chat.completions.create(**request).choices[0]

        assistant_msg = Message(role=Role.ASSISTANT, content="")
        if choice.message.content:
            assistant_msg.content = choice.message.content
        if choice.message.tool_calls:
            assistant_msg.tool_calls = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
                for tool_call in choice.message.tool_calls
            ]

        if choice.finish_reason == "tool_calls":
            messages.append(assistant_msg)
            tool_messages = await self._dispatch_tool_calls(choice.message.tool_calls)
            messages.extend(tool_messages)
            if log_messages:
                print("\n--- TOOL RESULTS ---")
                print(json.dumps([msg.to_dict() for msg in tool_messages], indent=2, default=str))
            return await self._chat_completion(messages, log_messages)

        if log_messages:
            print("\n--- RESPONSE ---")
        print(f"🤖: {assistant_msg.content}")
        return assistant_msg

    async def _dispatch_tool_calls(self, tool_calls) -> list[Message]:
        tool_messages: list[Message] = []
        for tool_call in tool_calls:
            tool = self._tools.get(tool_call.function.name)
            if tool is None:
                content = f"ERROR: unknown tool '{tool_call.function.name}'"
            else:
                arguments = json.loads(tool_call.function.arguments or "{}")
                print(f"    🔧 Calling `{tool_call.function.name}` with {arguments}")
                tool_message = await tool.execute(tool_call.id, arguments)
                content = tool_message.content

            tool_messages.append(Message(
                role=Role.TOOL,
                tool_call_id=tool_call.id,
                name=tool_call.function.name,
                content=content,
            ))
        return tool_messages
