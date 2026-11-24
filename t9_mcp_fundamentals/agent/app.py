import os
import sys
import asyncio
import json
from pathlib import Path

from mcp import Resource
from mcp.types import Prompt

from commons.constants import OPENAI_API_KEY, OPENAI_TERRA_MODEL
from commons.models.message import Message
from commons.models.role import Role
from t9_mcp_fundamentals.agent.agent import AgentMCPFundamentals
from t9_mcp_fundamentals.agent.mcp_clients.http import HttpMCPClient
from t9_mcp_fundamentals.agent.mcp_clients.stdio import StdioMCPClient
from t9_mcp_fundamentals.agent.prompts import SYSTEM_PROMPT

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STDIO_SERVER_PATH = PROJECT_ROOT / "t9_mcp_fundamentals" / "mcp_server" / "stdio_server.py"

# MCP_TRANSPORT=http (default), stdio (local users-management server over STDIO) or ddg-docker
# (STDIO MCP server from the docker image mcp/duckduckgo:latest)
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "http").lower()
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8005/mcp")


def create_mcp_client():
    if MCP_TRANSPORT == "stdio":
        return StdioMCPClient(
            command=sys.executable,  # use the same venv Python, not bare "python"
            args=[str(STDIO_SERVER_PATH)],
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}  # inherit env + add project root
        )
    if MCP_TRANSPORT == "ddg-docker":
        return StdioMCPClient(docker_image="mcp/duckduckgo:latest")
    return HttpMCPClient(mcp_server_url=MCP_SERVER_URL)


async def main():
    async with create_mcp_client() as mcp_client:
        # Resources
        resources: list[Resource] = await mcp_client.get_resources()
        print("\nAvailable Resources:")
        for resource in resources:
            print(f"  - {resource.uri} ({resource.name}, {resource.mime_type})")

        # Tools
        tools = await mcp_client.get_tools()
        print("\nAvailable Tools:")
        for tool in tools:
            print(f"  - {tool['function']['name']}: {tool['function']['description']}")

        agent = AgentMCPFundamentals(
            api_key=OPENAI_API_KEY,
            model=OPENAI_TERRA_MODEL,
            tools=tools,
            mcp_client=mcp_client
        )

        messages: list[Message] = [Message(role=Role.SYSTEM, content=SYSTEM_PROMPT)]

        # Prompts
        prompts: list[Prompt] = await mcp_client.get_prompts()
        print("\nAvailable Prompts:")
        for prompt in prompts:
            print(f"  - {prompt.name}: {prompt.description}")

        print("\nType 'exit' to quit.")
        while True:
            user_input = input("\n> ").strip()
            if user_input.lower() == 'exit':
                break
            if not user_input:
                continue

            messages.append(Message(role=Role.USER, content=user_input))
            ai_message = await agent.get_response(messages)
            messages.append(ai_message)


if __name__ == "__main__":
    asyncio.run(main())
